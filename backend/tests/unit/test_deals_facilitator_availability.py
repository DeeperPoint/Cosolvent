"""Tests for facilitator queue/availability surfacing (GAP-19)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.deals import service


# ── _facilitator_availability (pure) ──────────────────────────────────────────

def test_availability_none_when_neither_field_present():
    assert service._facilitator_availability({"company_name": "Acme"}) is None


def test_availability_surfaces_queue_depth_only():
    out = service._facilitator_availability({"queue_depth": 12})
    assert out == {"queue_depth": 12}


def test_availability_surfaces_available_from_only():
    out = service._facilitator_availability({"available_from": "2026-10-01"})
    assert out == {"available_from": "2026-10-01"}


def test_availability_surfaces_both():
    out = service._facilitator_availability({"queue_depth": 4, "available_from": "2026-09-15"})
    assert out == {"queue_depth": 4, "available_from": "2026-09-15"}


def test_availability_ignores_non_numeric_queue_depth():
    # A malformed value shouldn't crash or be surfaced as a fake number.
    out = service._facilitator_availability({"queue_depth": "soon"})
    assert out is None


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
