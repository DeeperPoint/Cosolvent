"""Business logic for the reference library: ingestion and domain retrieval."""

from __future__ import annotations

import logging

from app.modules.ai.embedding_client import get_embeddings_batch
from app.modules.knowledge import repository as repo
from app.modules.knowledge.schemas import (
    IngestResponse,
    ReferenceDocumentInput,
    RetrievalResult,
    RetrieveResponse,
)

logger = logging.getLogger("cosolvent.knowledge")


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


async def delete_document(doc_key: str) -> bool:
    """Remove a reference document and its chunks (FK cascade)."""
    return await repo.delete_document(doc_key)


async def stats(vertical: str | None = None) -> dict:
    """Lightweight library stats for admin/monitoring."""
    return {"vertical": vertical, "chunk_count": await repo.count_chunks(vertical)}
