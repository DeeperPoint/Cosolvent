"""Tests for facilitator queue/availability surfacing (GAP-19)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.deals import service

NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


# ── _facilitator_availability (pure) ──────────────────────────────────────────

def test_availability_none_when_neither_field_present():
    assert service._facilitator_availability({"company_name": "Acme"}) is None


def test_availability_surfaces_queue_depth_only():
    out = service._facilitator_availability({"queue_depth": 12})
    assert out == {"queue_depth": 12}


def test_availability_surfaces_available_from_only():
    out = service._facilitator_availability({"available_from": "2026-10-01"}, now=NOW)
    assert out == {"available_from": "2026-10-01", "days_until_available": 23}


def test_availability_surfaces_both():
    out = service._facilitator_availability(
        {"queue_depth": 4, "available_from": "2026-09-15"}, now=NOW
    )
    assert out == {"queue_depth": 4, "available_from": "2026-09-15", "days_until_available": 7}


def test_availability_ignores_non_numeric_queue_depth():
    # A malformed value shouldn't crash or be surfaced as a fake number.
    out = service._facilitator_availability({"queue_depth": "soon"})
    assert out is None


def test_availability_ignores_bool_queue_depth():
    # bool is a subclass of int in Python; a stray True/False must not pass as a queue depth.
    out = service._facilitator_availability({"queue_depth": True})
    assert out is None


def test_availability_days_until_available_floors_at_zero_for_a_past_date():
    # A facilitator whose declared date has already passed reads as free today,
    # not "was free three weeks ago" — a negative number would rank them as more
    # available than someone free right now, which is backwards.
    out = service._facilitator_availability({"available_from": "2026-08-01"}, now=NOW)
    assert out == {"available_from": "2026-08-01", "days_until_available": 0}


def test_availability_drops_an_unparseable_available_from():
    out = service._facilitator_availability({"available_from": "next Tuesday"}, now=NOW)
    assert out is None


def test_availability_drops_unparseable_available_from_but_keeps_queue_depth():
    out = service._facilitator_availability(
        {"queue_depth": 5, "available_from": "not-a-date"}, now=NOW
    )
    assert out == {"queue_depth": 5}


class TestAvailabilitySortKey:
    def _entry(self, **availability):
        return {"availability": availability} if availability else {}

    def test_sooner_available_from_ranks_first(self):
        soon = self._entry(days_until_available=2, queue_depth=10)
        later = self._entry(days_until_available=9, queue_depth=1)
        assert service._availability_sort_key(soon) < service._availability_sort_key(later)

    def test_queue_depth_breaks_a_tie_on_days_until_available(self):
        shallow = self._entry(days_until_available=3, queue_depth=1)
        deep = self._entry(days_until_available=3, queue_depth=8)
        assert service._availability_sort_key(shallow) < service._availability_sort_key(deep)

    def test_any_signal_outranks_no_signal_at_all(self):
        has_queue_only = self._entry(queue_depth=50)
        nothing = self._entry()
        assert service._availability_sort_key(has_queue_only) < service._availability_sort_key(nothing)


# ── search_facilitators: availability tie-break (previously untested — this path
#    used to return raw vector order with no availability tie-break at all) ─────

def _hit(pid: str, score: float, queue_depth: float | None = None) -> dict:
    fields = {"company_name": pid}
    if queue_depth is not None:
        fields["queue_depth"] = queue_depth
    return {"id": pid, "score": score, "profile": {"user_id": f"u-{pid}", "fields": fields}}


@pytest.mark.asyncio
async def test_search_facilitators_breaks_tied_scores_by_shorter_queue():
    hits = [
        _hit("slow", 0.9, queue_depth=30),
        _hit("fast", 0.9, queue_depth=2),
    ]
    with patch("app.modules.deals.repository.list_versions", new=AsyncMock(return_value=[])), \
         patch("app.modules.ai.embedding_client.get_embedding", new=AsyncMock(return_value=[0.1])), \
         patch("app.modules.discovery.vector_service.search_profile_vectors_strict",
               new=AsyncMock(return_value=hits)):
        results = await service.search_facilitators({"_id": "d1", "context": "x"}, "inspector", config=None)
    assert [r["profile_id"] for r in results] == ["fast", "slow"]


@pytest.mark.asyncio
async def test_search_facilitators_preserves_vector_order_when_scores_differ():
    # The higher semantic score wins regardless of availability -> availability is
    # strictly a tie-break, never a ranking override.
    hits = [
        _hit("best_match", 0.95, queue_depth=99),
        _hit("more_available", 0.60, queue_depth=1),
    ]
    with patch("app.modules.deals.repository.list_versions", new=AsyncMock(return_value=[])), \
         patch("app.modules.ai.embedding_client.get_embedding", new=AsyncMock(return_value=[0.1])), \
         patch("app.modules.discovery.vector_service.search_profile_vectors_strict",
               new=AsyncMock(return_value=hits)):
        results = await service.search_facilitators({"_id": "d1", "context": "x"}, "inspector", config=None)
    assert [r["profile_id"] for r in results] == ["best_match", "more_available"]


# ── search_facilitators_by_name: surfacing + tie-break ────────────────────────

def _profile(pid: str, company: str, queue_depth: float | None = None) -> dict:
    fields = {"company_name": company}
    if queue_depth is not None:
        fields["queue_depth"] = queue_depth
    return {"_id": pid, "user_id": f"u-{pid}", "fields": fields}


@pytest.mark.asyncio
async def test_search_by_name_surfaces_availability_on_candidates():
    profiles = [_profile("p1", "Acme Inspectors", queue_depth=8)]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=profiles)):
        results = await service.search_facilitators_by_name("inspector", "Acme")
    assert results[0]["availability"] == {"queue_depth": 8}


@pytest.mark.asyncio
async def test_search_by_name_breaks_score_ties_by_shorter_queue():
    # Both are substring (not exact) matches on "Inspect" -> tied score 0.9.
    profiles = [
        _profile("slow", "Inspect Co Slow", queue_depth=30),
        _profile("fast", "Inspect Co Fast", queue_depth=2),
    ]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=profiles)):
        results = await service.search_facilitators_by_name("inspector", "Inspect")
    assert [r["profile_id"] for r in results] == ["fast", "slow"]


@pytest.mark.asyncio
async def test_search_by_name_candidate_without_availability_sorts_after_none_missing():
    # A candidate with no queue_depth data treats as "unknown" (worst case, sorts last
    # among same-score ties) rather than crashing on a missing key.
    profiles = [
        _profile("known", "Beta Labs", queue_depth=5),
        _profile("unknown", "Beta Labs Two"),
    ]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=profiles)):
        results = await service.search_facilitators_by_name("inspector", "Beta")
    assert [r["profile_id"] for r in results] == ["known", "unknown"]


@pytest.mark.asyncio
async def test_search_by_name_available_from_only_no_longer_ties_with_no_data():
    # Previously the tie-break read only queue_depth, so a candidate who reported
    # *just* available_from ranked identically to one with no availability data at
    # all — the fix this test guards.
    profiles = [
        _profile("no_data", "Gamma Labs One"),
        {**_profile("has_date", "Gamma Labs Two"), "fields": {
            "company_name": "Gamma Labs Two", "available_from": "2020-01-01",
        }},
    ]
    with patch("app.modules.profiles.repository.list_profiles", new=AsyncMock(return_value=profiles)):
        results = await service.search_facilitators_by_name("inspector", "Gamma")
    assert [r["profile_id"] for r in results] == ["has_date", "no_data"]
