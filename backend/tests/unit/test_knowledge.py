"""Unit tests for the Knowledge Slot / Reference Library module.

Fast and isolated: the database and embedding provider are mocked, so these
exercise the loader grouping logic and the service ingest/retrieve flow without
any infrastructure.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.knowledge import loader, service
from app.modules.knowledge.schemas import ReferenceChunkInput, ReferenceDocumentInput


# ── loader.parse_records (pure) ───────────────────────────────────────────────

def _chunk(chunk_id, source_document=None, topic="general", embedding=None):
    meta = {"doc_type": "contract", "standard": "GAFTA", "jurisdiction": ["Canada"], "topic": topic}
    if source_document is not None:
        meta["source_document"] = source_document
    return {
        "chunk_id": chunk_id,
        "content": f"body of {chunk_id}",
        "contextual_content": f"[ctx] {chunk_id}",
        "metadata": meta,
        "embedding": embedding,
    }


def test_parse_records_groups_chunks_by_source_document():
    recs = [
        _chunk("27_2025_0", source_document="27_2025.md"),
        _chunk("27_2025_1", source_document="27_2025.md"),
    ]
    docs = loader.parse_records(recs, vertical="grain")
    assert len(docs) == 1
    assert docs[0].doc_key == "27_2025"
    assert docs[0].vertical == "grain"
    assert len(docs[0].chunks) == 2


def test_parse_records_doc_key_falls_back_to_chunk_id_prefix():
    docs = loader.parse_records([_chunk("abc_3")], vertical="grain")
    assert docs[0].doc_key == "abc"


def test_parse_records_promotes_doc_level_metadata_but_not_topic():
    docs = loader.parse_records([_chunk("d_0", source_document="d.md", topic="payment_terms")])
    dm = docs[0].doc_metadata
    assert dm["standard"] == "GAFTA"
    assert dm["doc_type"] == "contract"
    assert "topic" not in dm  # topic is chunk-level only


def test_parse_records_passes_embeddings_through():
    docs = loader.parse_records([_chunk("d_0", source_document="d.md", embedding=[0.1, 0.2, 0.3])])
    assert docs[0].chunks[0].embedding == [0.1, 0.2, 0.3]


def test_parse_jsonl_text_skips_blank_lines():
    text = '{"chunk_id":"d_0","content":"a","contextual_content":"c","metadata":{},"embedding":[0.1]}\n\n'
    docs = loader.parse_jsonl_text(text)
    assert len(docs) == 1 and len(docs[0].chunks) == 1


# ── service.ingest_documents ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_embeds_only_missing_chunks_and_counts():
    doc = ReferenceDocumentInput(
        doc_key="d",
        vertical="grain",
        chunks=[
            ReferenceChunkInput(chunk_id="d_0", content="a", contextual_content="ctx a", embedding=[0.9]),
            ReferenceChunkInput(chunk_id="d_1", content="b", contextual_content="ctx b"),  # missing
        ],
    )

    with (
        patch.object(service, "get_embeddings_batch", new=AsyncMock(return_value=[[0.5]])) as embed,
        patch.object(service.repo, "upsert_document", new=AsyncMock(return_value=uuid.uuid4())) as up_doc,
        patch.object(service.repo, "upsert_chunks", new=AsyncMock(side_effect=lambda _id, rows: len(rows))) as up_ch,
    ):
        resp = await service.ingest_documents([doc])

    # Only the embedding-less chunk is embedded, in one batched call.
    embed.assert_awaited_once_with(["ctx b"])
    assert doc.chunks[1].embedding == [0.5]
    assert doc.chunks[0].embedding == [0.9]  # untouched
    up_doc.assert_awaited_once()
    up_ch.assert_awaited_once()
    assert resp.documents_upserted == 1
    assert resp.chunks_upserted == 2


@pytest.mark.asyncio
async def test_ingest_skips_embedding_when_all_present():
    doc = ReferenceDocumentInput(
        doc_key="d",
        chunks=[ReferenceChunkInput(chunk_id="d_0", content="a", contextual_content="ctx", embedding=[0.1])],
    )
    with (
        patch.object(service, "get_embeddings_batch", new=AsyncMock()) as embed,
        patch.object(service.repo, "upsert_document", new=AsyncMock(return_value=uuid.uuid4())),
        patch.object(service.repo, "upsert_chunks", new=AsyncMock(return_value=1)),
    ):
        await service.ingest_documents([doc])
    embed.assert_not_awaited()


# ── service.retrieve ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_embeds_query_and_maps_results():
    row = {
        "chunk_id": "27_2025_3",
        "doc_key": "27_2025",
        "title": "GAFTA Contract No. 27",
        "source_document": "27_2025.md",
        "content": "payment terms...",
        "contextual_content": "[ctx] payment terms...",
        "score": 0.83,
        "metadata": {"topic": "payment_terms", "standard": "GAFTA"},
    }
    with (
        patch.object(service, "get_embeddings_batch", new=AsyncMock(return_value=[[0.1, 0.2]])) as embed,
        patch.object(service.repo, "retrieve", new=AsyncMock(return_value=[row])) as ret,
    ):
        resp = await service.retrieve(query="how do payments work?", filters={"topic": "payment_terms"}, vertical="grain", top_k=5)

    embed.assert_awaited_once_with(["how do payments work?"])
    ret.assert_awaited_once()
    # Filters/vertical/top_k are forwarded to the repository.
    assert ret.call_args.kwargs["vertical"] == "grain"
    assert ret.call_args.kwargs["top_k"] == 5
    assert ret.call_args.kwargs["filters"] == {"topic": "payment_terms"}
    assert resp.query == "how do payments work?"
    assert len(resp.results) == 1
    assert resp.results[0].chunk_id == "27_2025_3"
    assert resp.results[0].score == 0.83
