"""Unit tests for domain Q&A and knowledge-gap capture.

Retrieval, the LLM, and the database are mocked, so these isolate the grounded
answer/citation logic and the gap-signal branching.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.knowledge import service
from app.modules.knowledge.schemas import RetrievalResult, RetrieveResponse


def _result(chunk_id="27_2025_3", doc_key="27_2025", topic="payment_terms"):
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_key=doc_key,
        title="GAFTA Contract No. 27",
        source_document="27_2025.md",
        content="Payment is due against shipping documents.",
        contextual_content="[27_2025.md] 13. PAYMENT > Payment is due against shipping documents.",
        score=0.82,
        metadata={"topic": topic, "standard": "GAFTA"},
    )


def _retrieval(results):
    return RetrieveResponse(query="q", results=results)


@pytest.mark.asyncio
async def test_ask_returns_grounded_answer_with_citations():
    with (
        patch.object(service, "retrieve", new=AsyncMock(return_value=_retrieval([_result()]))),
        patch.object(service, "generate", new=AsyncMock(return_value="Payment is due against documents [27_2025].")),
        patch.object(service.repo, "insert_gap_signal", new=AsyncMock()) as gap,
    ):
        resp = await service.ask(query="when is payment due?", vertical="grain")

    assert resp.answered is True
    assert "[27_2025]" in resp.answer
    assert resp.used_chunks == ["27_2025_3"]
    assert len(resp.citations) == 1
    assert resp.citations[0].doc_key == "27_2025"
    assert resp.citations[0].chunk_ids == ["27_2025_3"]
    gap.assert_not_awaited()  # answered -> no gap recorded


@pytest.mark.asyncio
async def test_ask_with_no_matching_chunks_records_gap_and_skips_llm():
    with (
        patch.object(service, "retrieve", new=AsyncMock(return_value=_retrieval([]))),
        patch.object(service, "generate", new=AsyncMock()) as llm,
        patch.object(service.repo, "insert_gap_signal", new=AsyncMock()) as gap,
    ):
        resp = await service.ask(query="what is the tariff on widgets?", vertical="grain", filters={"topic": "x"})

    llm.assert_not_awaited()  # nothing retrieved -> don't pay for an LLM call
    gap.assert_awaited_once()
    assert gap.call_args.kwargs["reason"] == "no_matching_chunks"
    assert resp.answered is False
    assert resp.answer == service._NOT_COVERED_MSG


@pytest.mark.asyncio
async def test_ask_when_model_reports_not_covered_records_gap():
    with (
        patch.object(service, "retrieve", new=AsyncMock(return_value=_retrieval([_result()]))),
        patch.object(service, "generate", new=AsyncMock(return_value="NOT_COVERED")),
        patch.object(service.repo, "insert_gap_signal", new=AsyncMock()) as gap,
    ):
        resp = await service.ask(query="unrelated question?", vertical="grain")

    gap.assert_awaited_once()
    assert gap.call_args.kwargs["reason"] == "model_not_covered"
    assert resp.answered is False
    assert resp.used_chunks == ["27_2025_3"]
    assert resp.citations == []


@pytest.mark.asyncio
async def test_ask_gap_logging_failure_does_not_break_answer_path():
    # A failure recording the gap must not surface to the caller.
    with (
        patch.object(service, "retrieve", new=AsyncMock(return_value=_retrieval([]))),
        patch.object(service.repo, "insert_gap_signal", new=AsyncMock(side_effect=RuntimeError("db down"))),
    ):
        resp = await service.ask(query="anything?")
    assert resp.answered is False


def test_extract_citations_only_returns_referenced_docs():
    chunks = [_result(chunk_id="a_0", doc_key="a"), _result(chunk_id="b_0", doc_key="b")]
    cites = service._extract_citations("Per [a], yes.", chunks)
    assert [c.doc_key for c in cites] == ["a"]
    assert cites[0].chunk_ids == ["a_0"]


def test_extract_citations_groups_multiple_chunks_per_doc():
    chunks = [_result(chunk_id="a_0", doc_key="a"), _result(chunk_id="a_1", doc_key="a")]
    cites = service._extract_citations("See [a].", chunks)
    assert len(cites) == 1
    assert cites[0].chunk_ids == ["a_0", "a_1"]


@pytest.mark.asyncio
async def test_list_gaps_maps_rows():
    rows = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "query": "tariff on widgets?",
            "vertical": "grain",
            "filters": {"topic": "x"},
            "reason": "no_matching_chunks",
            "created_at": "2026-06-08T10:00:00+00:00",
        }
    ]
    with patch.object(service.repo, "list_gap_signals", new=AsyncMock(return_value=rows)):
        out = await service.list_gaps(vertical="grain")
    assert len(out.gaps) == 1
    assert out.gaps[0].reason == "no_matching_chunks"
    assert out.gaps[0].query == "tariff on widgets?"
