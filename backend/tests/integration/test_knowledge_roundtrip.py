"""Live pgvector round-trip for the reference library + gap signals.

Deterministic and provider-free: chunks are ingested with a precomputed
embedding and retrieved with a fixed query vector, so no LLM/embedding provider
is required — only a migrated Postgres+pgvector database.

Gated by RUN_INTEGRATION (skipped in the normal unit run).
"""

from __future__ import annotations

import pytest

from app.core.database import close_db, connect_db
from app.modules.knowledge import repository as repo
from app.modules.knowledge.schemas import ReferenceChunkInput, ReferenceDocumentInput
from app.modules.knowledge import service
from tests.e2e.helpers import require_mode

DIM = 1536


def _vec(seed: float) -> list[float]:
    return [seed] * DIM


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_retrieve_and_gap_roundtrip():
    require_mode("RUN_INTEGRATION")
    await connect_db()
    try:
        doc = ReferenceDocumentInput(
            doc_key="it_27_2025",
            vertical="grain",
            title="GAFTA Contract No. 27",
            source_document="it_27_2025.md",
            doc_metadata={"doc_type": "contract", "standard": "GAFTA"},
            chunks=[
                ReferenceChunkInput(
                    chunk_id="it_27_2025_0",
                    content="Payment is due against shipping documents.",
                    contextual_content="[it_27_2025.md] 13. PAYMENT > due against documents",
                    metadata={"topic": "payment_terms", "jurisdiction": ["Canada"]},
                    embedding=_vec(0.01),
                ),
            ],
        )

        # Ingest is idempotent: run twice, expect a single chunk row.
        await service.ingest_documents([doc])
        await service.ingest_documents([doc])

        hits = await repo.retrieve(_vec(0.01), top_k=5, filters={"topic": "payment_terms"}, vertical="grain")
        assert any(h["chunk_id"] == "it_27_2025_0" for h in hits)
        top = next(h for h in hits if h["chunk_id"] == "it_27_2025_0")
        assert top["doc_key"] == "it_27_2025"
        assert top["title"] == "GAFTA Contract No. 27"

        # Metadata pre-filter excludes non-matching topics.
        none = await repo.retrieve(_vec(0.01), top_k=5, filters={"topic": "no_such_topic"}, vertical="grain")
        assert all(h["chunk_id"] != "it_27_2025_0" for h in none)

        # Gap-signal round-trip.
        await repo.insert_gap_signal(
            query="tariff on widgets?", vertical="grain", filters={"topic": "x"}, reason="no_matching_chunks"
        )
        gaps = await repo.list_gap_signals(vertical="grain", limit=10)
        assert any(g["query"] == "tariff on widgets?" and g["reason"] == "no_matching_chunks" for g in gaps)

        # Cleanup.
        await repo.delete_document("it_27_2025")
    finally:
        await close_db()
