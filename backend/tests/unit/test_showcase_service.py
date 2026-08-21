"""Tests for the showcase precompute cache (MarketForge Phase 6a 'Mode 1')."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.marketplace_config import load_marketplace_config
from app.modules.showcase import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand, recruiter=facilitator (talent.yaml)
    return load_marketplace_config(FIXTURES / "talent.yaml")


def _profile(pid: str, user_id: str, synthetic: bool = True) -> dict:
    return {"_id": pid, "user_id": user_id, "is_synthetic": synthetic, "fields": {"company_name": f"Co {pid}"}}


# ── _precompute_matches_for_type ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_precompute_matches_only_considers_synthetic_profiles():
    profiles = [_profile("p1", "u1", synthetic=True), _profile("p2", "u2", synthetic=False)]
    with patch.object(service.profiles_repo, "list_profiles", new=AsyncMock(return_value=profiles)), \
         patch.object(service.discovery_matching, "suggested_matches",
                       new=AsyncMock(return_value={"results": []})) as sm, \
         patch.object(service.repo, "upsert", new=AsyncMock()):
        personas, matches, errors = await service._precompute_matches_for_type(_cfg(), "candidate")

    assert personas == 1
    assert matches == 1
    assert errors == []
    sm.assert_awaited_once()
    # Only the synthetic profile's user_id is used as the viewer (owner check).
    assert sm.await_args.kwargs["viewer"]["_id"] == "u1"


@pytest.mark.asyncio
async def test_precompute_matches_caches_scores_and_breakdown():
    profiles = [_profile("p1", "u1")]
    result = {"results": [
        {"id": "cand1", "participant_type": "employer", "fields": {"company_name": "Acme"},
         "score": 0.87, "score_breakdown": {"vector": 0.9}},
    ]}
    upserts = []
    with patch.object(service.profiles_repo, "list_profiles", new=AsyncMock(return_value=profiles)), \
         patch.object(service.discovery_matching, "suggested_matches", new=AsyncMock(return_value=result)), \
         patch.object(service.repo, "upsert", new=AsyncMock(side_effect=lambda *a: upserts.append(a))):
        await service._precompute_matches_for_type(_cfg(), "candidate")

    match_upsert = next(u for u in upserts if u[0] == "matches")
    cached = match_upsert[2]["matches"][0]
    assert cached["candidate_profile_id"] == "cand1"
    assert cached["score"] == 0.87
    assert cached["score_breakdown"] == {"vector": 0.9}


@pytest.mark.asyncio
async def test_precompute_matches_is_non_fatal_per_profile():
    """One profile's matching failure (e.g. not indexed yet) doesn't sink the batch."""
    profiles = [_profile("bad", "u-bad"), _profile("good", "u-good")]

    async def _sm(config, *, profile_id, **kwargs):
        if profile_id == "bad":
            raise RuntimeError("not indexed yet")
        return {"results": []}

    with patch.object(service.profiles_repo, "list_profiles", new=AsyncMock(return_value=profiles)), \
         patch.object(service.discovery_matching, "suggested_matches", new=AsyncMock(side_effect=_sm)), \
         patch.object(service.repo, "upsert", new=AsyncMock()):
        personas, matches, errors = await service._precompute_matches_for_type(_cfg(), "candidate")

    assert personas == 1  # only "good"
    assert matches == 1
    assert len(errors) == 1
    assert "bad" in errors[0]


# ── _precompute_qa_for_type ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_precompute_qa_caches_one_entry_per_template():
    fake_answer = MagicMock(answer="text", answered=True, citations=[])
    upserts = []
    with patch.object(service.knowledge_service, "ask", new=AsyncMock(return_value=fake_answer)) as ask, \
         patch.object(service.repo, "upsert", new=AsyncMock(side_effect=lambda *a: upserts.append(a))):
        cached, errors = await service._precompute_qa_for_type(_cfg(), "candidate", "Candidate")

    assert cached == len(service._QA_TEMPLATES)
    assert errors == []
    # vertical is never passed as a (possibly mismatched) marketplace display name —
    # see the docstring note in _precompute_qa_for_type.
    for call in ask.await_args_list:
        assert call.kwargs["vertical"] is None


@pytest.mark.asyncio
async def test_precompute_qa_is_non_fatal_per_question():
    with patch.object(service.knowledge_service, "ask", new=AsyncMock(side_effect=RuntimeError("no key"))), \
         patch.object(service.repo, "upsert", new=AsyncMock()):
        cached, errors = await service._precompute_qa_for_type(_cfg(), "candidate", "Candidate")

    assert cached == 0
    assert len(errors) == len(service._QA_TEMPLATES)


# ── run_precompute: end-to-end wiring ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_precompute_clears_then_rebuilds_all_three_kinds():
    clear_calls = []
    with patch.object(service.repo, "clear", new=AsyncMock(side_effect=lambda k: clear_calls.append(k))), \
         patch.object(service, "_precompute_matches_for_type", new=AsyncMock(return_value=(2, 2, []))), \
         patch.object(service, "_precompute_qa_for_type", new=AsyncMock(return_value=(2, []))):
        result = await service.run_precompute(_cfg())

    assert set(clear_calls) == {"persona", "matches", "qa"}
    # talent.yaml has 3 participant types -> 3x matches + 3x qa calls.
    assert result.personas_cached == 6
    assert result.matches_cached == 6
    assert result.qa_cached == 6
    assert result.generated_at


# ── read helpers ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_matches_returns_empty_list_when_uncached():
    with patch.object(service.repo, "get", new=AsyncMock(return_value=None)):
        assert await service.get_matches("candidate", "missing") == []


@pytest.mark.asyncio
async def test_get_personas_scopes_by_participant_type_prefix():
    with patch.object(service.repo, "list_by_kind_prefix", new=AsyncMock(return_value=[{"profile_id": "p1"}])) as lbp:
        result = await service.get_personas("candidate", limit=10)
    lbp.assert_awaited_once_with("persona", "candidate:", limit=10)
    assert result == [{"profile_id": "p1"}]
