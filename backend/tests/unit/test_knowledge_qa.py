"""Unit tests for grounded reference-library Q&A and gap capture.

Embedding, retrieval, the LLM, and the DB are mocked, so these isolate the
grounding/citation logic and the gap-signal branching.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.knowledge import service


def _hit(row_id="r1", key="27_2025", text="[27_2025.md] 13. PAYMENT > Payment is due against documents.",
         topic="payment_terms"):
    return {
        "id": row_id,
        "chunk_text": text,
        "metadata": {"source_doc_id": key, "topic": topic, "source_layer": "wiki"},
        "score": 0.82,
    }


def _patch(hits, answer):
    return (
        patch.object(service, "get_embedding", new=AsyncMock(return_value=[0.01] * 1536)),
        patch.object(service, "search_reference_library", new=AsyncMock(return_value=hits)),
        patch.object(service, "generate", new=AsyncMock(return_value=answer)),
        patch.object(service, "_record_gap", new=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_ask_returns_grounded_answer_with_citations():
    p_emb, p_search, p_gen, p_gap = _patch([_hit()], "Payment is due against documents [27_2025].")
    with p_emb, p_search, p_gen, p_gap as gap:
        resp = await service.ask(query="when is payment due?", vertical="grain")

    assert resp.answered is True
    assert resp.used_chunks == ["r1"]
    assert len(resp.citations) == 1
    assert resp.citations[0].key == "27_2025"
    assert resp.citations[0].source_doc_id == "27_2025"
    assert resp.citations[0].chunk_ids == ["r1"]
    gap.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_no_hits_records_gap_and_skips_llm():
    p_emb, p_search, p_gen, p_gap = _patch([], "unused")
    with p_emb, p_search, p_gen as gen, p_gap as gap:
        resp = await service.ask(query="tariff on widgets?", vertical="grain")

    gen.assert_not_awaited()
    gap.assert_awaited_once()
    assert gap.call_args.args[3] == "no_matching_chunks"
    assert resp.answered is False
    assert resp.answer == service._NOT_COVERED_MSG


@pytest.mark.asyncio
async def test_ask_model_not_covered_records_gap():
    p_emb, p_search, p_gen, p_gap = _patch([_hit()], "NOT_COVERED")
    with p_emb, p_search, p_gen, p_gap as gap:
        resp = await service.ask(query="unrelated?", vertical="grain")

    gap.assert_awaited_once()
    assert gap.call_args.args[3] == "model_not_covered"
    assert resp.answered is False
    assert resp.citations == []


@pytest.mark.asyncio
async def test_ask_without_citations_is_not_answered_and_records_gap():
    p_emb, p_search, p_gen, p_gap = _patch([_hit()], "Payment is due against documents.")
    with p_emb, p_search, p_gen, p_gap as gap:
        resp = await service.ask(query="when is payment due?", vertical="grain")

    assert resp.answered is False
    assert resp.answer == service._NOT_COVERED_MSG
    assert resp.citations == []
    gap.assert_awaited_once()
    assert gap.call_args.args[3] == "answer_without_citation"


def test_format_context_strips_leading_marker():
    ctx = service._format_context([_hit()], ["27_2025"])
    assert "[27_2025]" in ctx                 # the citable key tag
    assert "[27_2025.md]" not in ctx          # rival marker stripped
    assert "Payment is due against documents." in ctx


def test_cite_key_prefers_source_doc_id_then_fallbacks():
    assert service._cite_key({"source_doc_id": "27_2025"}, 0) == "27_2025"
    assert service._cite_key({"source_document": "gafta_27.md"}, 0) == "gafta_27"
    assert service._cite_key({}, 3) == "ref4"


def test_extract_citations_maps_only_cited_keys():
    hits = [_hit(row_id="a", key="a"), _hit(row_id="b", key="b")]
    cites = service._extract_citations("Per [a], yes.", hits, ["a", "b"])
    assert [c.key for c in cites] == ["a"]
    assert cites[0].chunk_ids == ["a"]


def test_bounded_gap_limit_clamps_range():
    assert service.bounded_gap_limit(50) == 50
    assert service.bounded_gap_limit(10_000_000) == service._MAX_GAP_LIMIT
    assert service.bounded_gap_limit(0) == 1


def test_normalize_record_preserves_readable_source_id():
    row = service.normalize_record({
        "source_doc_id": "27_2025", "vertical": "grain",
        "chunk_text": "x", "embedding": [0.1, 0.2], "metadata": {"topic": "payment_terms"},
    })
    assert row["reference_metadata"]["source_doc_id"] == "27_2025"
    assert row["reference_metadata"]["topic"] == "payment_terms"
