"""Business logic for the reference library: ingestion and domain retrieval."""

from __future__ import annotations

import logging
import re

from app.modules.ai.embedding_client import get_embeddings_batch
from app.modules.ai.llm_client import generate
from app.modules.knowledge import repository as repo
from app.modules.knowledge.schemas import (
    AskResponse,
    Citation,
    GapSignal,
    GapSignalList,
    IngestResponse,
    ReferenceDocumentInput,
    RetrievalResult,
    RetrieveResponse,
)

logger = logging.getLogger("cosolvent.knowledge")

# Sentinel the model must emit when the excerpts cannot answer the question.
_NOT_COVERED = "NOT_COVERED"
_NOT_COVERED_MSG = "This question isn't covered by the current reference library."

_GROUNDING_SYSTEM = (
    "You are a domain reference assistant for a curated knowledge library. "
    "Answer the question using ONLY the reference excerpts provided by the user. "
    "Cite every excerpt you rely on inline using its bracketed key, e.g. [27_2025]. "
    "Do not use any outside or prior knowledge. If the excerpts do not contain "
    f"enough information to answer, reply with exactly: {_NOT_COVERED}"
)

_CITATION_RE = re.compile(r"\[([^\]\n]+)\]")

# Leading source marker that KnowledgeSlot prepends to contextual_content
# (e.g. "[27_2025.md] 13. PAYMENT > ..."). It is stripped before the excerpt is
# shown to the model so the only bracketed token in an excerpt is its [doc_key]
# citation tag — otherwise the model may cite "[27_2025.md]", which does not map
# back to a doc_key.
_LEADING_MARKER_RE = re.compile(r"^\s*\[[^\]\n]+\]\s*")


async def ingest_documents(documents: list[ReferenceDocumentInput]) -> IngestResponse:
    """Upsert reference documents and their chunks.

    Chunks that arrive without a precomputed embedding are embedded here in a
    single batched call; chunks that already carry one (the normal case for
    KnowledgeSlot JSONL) are stored as-is.
    """
    docs_upserted = 0
    chunks_upserted = 0

    for doc in documents:
        await _ensure_embeddings(doc)

        doc_id = await repo.upsert_document(
            doc_key=doc.doc_key,
            vertical=doc.vertical,
            title=doc.title,
            source_document=doc.source_document,
            source_url=doc.source_url,
            doc_metadata=doc.doc_metadata,
        )
        docs_upserted += 1

        chunk_rows = [
            {
                "chunk_id": c.chunk_id,
                "content": c.content,
                "contextual_content": c.contextual_content,
                "embedding": c.embedding,
                "metadata": c.metadata,
            }
            for c in doc.chunks
        ]
        chunks_upserted += await repo.upsert_chunks(doc_id, chunk_rows)

    return IngestResponse(documents_upserted=docs_upserted, chunks_upserted=chunks_upserted)


async def _ensure_embeddings(doc: ReferenceDocumentInput) -> None:
    """Embed any chunks missing a vector, in one batched provider call."""
    missing = [c for c in doc.chunks if not c.embedding]
    if not missing:
        return
    vectors = await get_embeddings_batch([c.contextual_content for c in missing])
    for chunk, vector in zip(missing, vectors):
        chunk.embedding = vector


async def retrieve(
    *,
    query: str,
    filters: dict | None = None,
    vertical: str | None = None,
    top_k: int = 8,
    min_score: float = 0.0,
) -> RetrieveResponse:
    """Embed the query and return the best-matching reference chunks with citations."""
    query_vec = (await get_embeddings_batch([query]))[0]
    rows = await repo.retrieve(
        query_vec,
        top_k=top_k,
        filters=filters,
        vertical=vertical,
        min_score=min_score,
    )
    results = [RetrievalResult(**row) for row in rows]
    return RetrieveResponse(query=query, results=results)


async def ask(
    *,
    query: str,
    filters: dict | None = None,
    vertical: str | None = None,
    top_k: int = 8,
    min_score: float = 0.0,
) -> AskResponse:
    """Answer a question strictly from the reference library, with citations.

    Retrieves the most relevant chunks, asks the LLM to answer using only those
    excerpts, and — when nothing matches or the model reports the answer is not
    covered — records a knowledge gap signal for curators.
    """
    retrieval = await retrieve(
        query=query, filters=filters, vertical=vertical, top_k=top_k, min_score=min_score
    )
    chunks = retrieval.results
    used_chunks = [c.chunk_id for c in chunks]

    if not chunks:
        await _record_gap(query, vertical, filters, "no_matching_chunks")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG)

    messages = [
        {"role": "system", "content": _GROUNDING_SYSTEM},
        {"role": "user", "content": f"Reference excerpts:\n\n{_format_context(chunks)}\n\nQuestion: {query}"},
    ]
    raw = (await generate(messages, use_case="rag_query")).strip()

    if raw.upper().startswith(_NOT_COVERED):
        await _record_gap(query, vertical, filters, "model_not_covered")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG, used_chunks=used_chunks)

    citations = _extract_citations(raw, chunks)
    if not citations:
        # The model produced prose but cited no retrievable [doc_key]. Under the
        # "grounded, with citations" contract that is not an answer we can stand
        # behind, so treat it as not covered and record a gap for curators.
        await _record_gap(query, vertical, filters, "answer_without_citation")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG, used_chunks=used_chunks)

    return AskResponse(
        query=query,
        answered=True,
        answer=raw,
        citations=citations,
        used_chunks=used_chunks,
    )


def _format_context(chunks: list[RetrievalResult]) -> str:
    """Render retrieved chunks as keyed excerpts the model can cite by [doc_key]."""
    blocks = []
    for c in chunks:
        topic = (c.metadata or {}).get("topic")
        tag = f"[{c.doc_key}]" + (f" (topic: {topic})" if topic else "")
        excerpt = _LEADING_MARKER_RE.sub("", c.contextual_content, count=1)
        blocks.append(f"{tag}\n{excerpt}")
    return "\n\n---\n\n".join(blocks)


def _extract_citations(answer: str, chunks: list[RetrievalResult]) -> list[Citation]:
    """Map the [doc_key] tokens the model used back to the retrieved documents."""
    cited = set(_CITATION_RE.findall(answer))
    by_key: dict[str, Citation] = {}
    for c in chunks:
        if c.doc_key not in cited:
            continue
        entry = by_key.get(c.doc_key)
        if entry is None:
            by_key[c.doc_key] = Citation(
                doc_key=c.doc_key,
                title=c.title,
                source_document=c.source_document,
                chunk_ids=[c.chunk_id],
            )
        else:
            entry.chunk_ids.append(c.chunk_id)
    return list(by_key.values())


async def _record_gap(query: str, vertical: str | None, filters: dict | None, reason: str) -> None:
    try:
        await repo.insert_gap_signal(query=query, vertical=vertical, filters=filters, reason=reason)
    except Exception:  # noqa: BLE001 - a gap-logging failure must not break the answer path.
        logger.warning("Failed to record knowledge gap signal", exc_info=True)


async def list_gaps(vertical: str | None = None, limit: int = 100) -> GapSignalList:
    """Curator view: recorded knowledge gaps, newest first."""
    rows = await repo.list_gap_signals(vertical=vertical, limit=limit)
    return GapSignalList(gaps=[GapSignal(**row) for row in rows])


async def delete_document(doc_key: str) -> bool:
    """Remove a reference document and its chunks (FK cascade)."""
    return await repo.delete_document(doc_key)


async def stats(vertical: str | None = None) -> dict:
    """Lightweight library stats for admin/monitoring."""
    return {"vertical": vertical, "chunk_count": await repo.count_chunks(vertical)}
