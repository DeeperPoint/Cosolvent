"""Tests for market-dynamics reporting (roadmap B1.8 'Market Physics Scorecard')."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.marketplace_config import load_marketplace_config
from app.modules.analytics import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand, recruiter=facilitator
    return load_marketplace_config(FIXTURES / "talent.yaml")


def _deal(status: str, instrument: str | None = None, slots: list[dict] | None = None) -> dict:
    return {"status": status, "instrument": instrument, "facilitator_slots": slots or []}


@pytest.fixture
def mock_repo():
    with patch("app.modules.analytics.service.repo") as mock:
        mock.profile_counts_by_type = AsyncMock(return_value={})
        mock.all_deals = AsyncMock(return_value=[])
        mock.all_story_version_states = AsyncMock(return_value=[])
        yield mock


# ── participant counts ───────────────────────────────────────────────────────

def test_counts_to_participants_splits_real_and_synthetic():
    by_type = {"candidate": {"real": 3, "synthetic": 5}, "employer": {"real": 2, "synthetic": 0}}
    result = service._counts_to_participants(by_type)
    assert result.total == 10
    assert result.real == 5
    assert result.synthetic == 5
    assert result.by_type == {"candidate": 8, "employer": 2}


def test_counts_to_participants_empty():
    result = service._counts_to_participants({})
    assert result.total == 0 and result.by_type == {}


# ── deal funnel ──────────────────────────────────────────────────────────────

def test_deal_funnel_empty_has_zero_rates():
    funnel = service._deal_funnel([])
    assert funnel.total == 0
    assert funnel.brief_reached_rate == 0.0
    assert funnel.handoff_rate == 0.0
    assert funnel.abandoned_rate == 0.0


def test_deal_funnel_computes_rates_and_breakdowns():
    deals = [
        _deal("active", "spot_purchase"),
        _deal("active", "spot_purchase"),
        _deal("brief_ready", "capacity_rental"),
        _deal("handoff", "spot_purchase"),
        _deal("closed"),
        _deal("cancelled"),
    ]
    funnel = service._deal_funnel(deals)
    assert funnel.total == 6
    assert funnel.by_status == {"active": 2, "brief_ready": 1, "handoff": 1, "closed": 1, "cancelled": 1}
    assert funnel.by_instrument == {"spot_purchase": 3, "capacity_rental": 1, "unset": 2}
    # brief_ready + handoff = 2 of 6 (rates are rounded to 4dp by the service)
    assert funnel.brief_reached_rate == pytest.approx(2 / 6, abs=1e-4)
    # handoff = 1 of 6
    assert funnel.handoff_rate == pytest.approx(1 / 6, abs=1e-4)
    # closed + cancelled = 2 of 6
    assert funnel.abandoned_rate == pytest.approx(2 / 6, abs=1e-4)


def test_deal_funnel_unset_instrument_and_unknown_status():
    deals = [{"status": None, "instrument": None, "facilitator_slots": []}]
    funnel = service._deal_funnel(deals)
    assert funnel.by_status == {"unknown": 1}
    assert funnel.by_instrument == {"unset": 1}


# ── facilitator utilization ───────────────────────────────────────────────────

def test_facilitator_utilization_counts_demand_and_supply():
    deals = [
        _deal("active", slots=[{"role_type": "recruiter", "status": "needed"}]),
        _deal("active", slots=[{"role_type": "recruiter", "status": "searching"}]),
        _deal("active", slots=[{"role_type": "recruiter", "status": "confirmed"}]),
        # Abandoned deals don't count as live demand.
        _deal("closed", slots=[{"role_type": "recruiter", "status": "needed"}]),
        _deal("cancelled", slots=[{"role_type": "recruiter", "status": "needed"}]),
    ]
    result = service._facilitator_utilization(deals, _cfg(), supply_by_type={"recruiter": 4})
    assert len(result) == 1
    row = result[0]
    assert row.role_type == "recruiter"
    assert row.demand_needed == 2  # "needed" + "searching", not the closed/cancelled ones
    assert row.demand_confirmed == 1
    assert row.supply_profiles == 4


def test_facilitator_utilization_lists_every_facilitator_role_even_with_no_deals():
    result = service._facilitator_utilization([], _cfg(), supply_by_type={})
    assert [r.role_type for r in result] == ["recruiter"]
    assert result[0].demand_needed == 0
    assert result[0].demand_confirmed == 0
    assert result[0].supply_profiles == 0


def test_facilitator_utilization_ignores_slot_for_role_not_in_config():
    deals = [_deal("active", slots=[{"role_type": "ghost_role", "status": "needed"}])]
    result = service._facilitator_utilization(deals, _cfg(), supply_by_type={})
    assert result[0].demand_needed == 0  # the ghost_role slot doesn't leak into recruiter's count


# ── story health ─────────────────────────────────────────────────────────────

def test_story_health_groups_by_state():
    states = ["published", "published", "milestone", "stale", "unknown"]
    health = service._story_health(states)
    assert health.by_state == {"published": 2, "milestone": 1, "stale": 1, "unknown": 1}


# ── end-to-end wiring ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_market_overview_wires_everything_together(mock_repo):
    mock_repo.profile_counts_by_type = AsyncMock(
        return_value={"recruiter": {"real": 1, "synthetic": 2}}
    )
    mock_repo.all_deals = AsyncMock(
        return_value=[_deal("handoff", "spot_purchase", [{"role_type": "recruiter", "status": "confirmed"}])]
    )
    mock_repo.all_story_version_states = AsyncMock(return_value=["milestone"])

    overview = await service.get_market_overview(_cfg())

    assert overview.participants.total == 3
    assert overview.deals.total == 1
    assert overview.deals.handoff_rate == 1.0
    assert overview.facilitators[0].role_type == "recruiter"
    assert overview.facilitators[0].demand_confirmed == 1
    assert overview.facilitators[0].supply_profiles == 3  # real + synthetic
    assert overview.story_versions.by_state == {"milestone": 1}
    assert overview.generated_at  # non-empty ISO timestamp


# ── match density ────────────────────────────────────────────────────────────

def test_opposite_type_pairs_is_supply_to_demand_only():
    # candidate=supply, employer=demand, recruiter=facilitator (talent.yaml)
    assert service._opposite_type_pairs(_cfg()) == [("candidate", "employer")]


@pytest.mark.asyncio
async def test_corridor_density_counts_pairs_and_isolated_profiles():
    with patch.object(service.repo, "active_profile_ids_by_type", new=AsyncMock(return_value=["p1", "p2", "p3"])), \
         patch("app.modules.discovery.vector_service.get_profile_embedding", new=AsyncMock(side_effect=[[0.1], [0.2], None])), \
         patch("app.modules.discovery.vector_service.find_similar_profiles", new=AsyncMock(side_effect=[
             [{"id": "c1", "score": 0.9}, {"id": "c2", "score": 0.8}],  # p1: 2 matches
             [],  # p2: isolated
         ])):
        result = await service._corridor_density("candidate", "employer", threshold=0.75, sample_limit=200)

    assert result.source_type == "candidate"
    assert result.target_type == "employer"
    # p3 has no embedding -> excluded from the sample entirely, not counted as isolated.
    assert result.source_sampled == 2
    assert result.pairs_above_threshold == 2
    assert result.isolated_source_profiles == 1
    assert result.average_top_score == pytest.approx(0.9)  # only p1 contributed a top score


@pytest.mark.asyncio
async def test_corridor_density_all_unindexed_yields_no_crash():
    with patch.object(service.repo, "active_profile_ids_by_type", new=AsyncMock(return_value=["p1"])), \
         patch("app.modules.discovery.vector_service.get_profile_embedding", new=AsyncMock(return_value=None)):
        result = await service._corridor_density("candidate", "employer", threshold=0.75, sample_limit=200)

    assert result.source_sampled == 0
    assert result.pairs_above_threshold == 0
    assert result.isolated_source_profiles == 0
    assert result.average_top_score is None


@pytest.mark.asyncio
async def test_get_match_density_wires_corridors_and_metadata():
    with patch.object(service, "_corridor_density", new=AsyncMock(return_value=service.CorridorDensity(
        source_type="candidate", target_type="employer", source_sampled=5,
        pairs_above_threshold=3, isolated_source_profiles=1, average_top_score=0.81,
    ))):
        density = await service.get_match_density(_cfg(), threshold=0.8, sample_limit=50)

    assert density.threshold == 0.8
    assert len(density.corridors) == 1
    assert density.corridors[0].pairs_above_threshold == 3
    assert density.generated_at
    assert "approximat" in density.note.lower() or "upper-bound" in density.note.lower()


@pytest.mark.asyncio
async def test_get_match_density_clamps_sample_limit_to_max():
    calls = []

    async def _fake_corridor(source_type, target_type, *, threshold, sample_limit):
        calls.append(sample_limit)
        return service.CorridorDensity(
            source_type=source_type, target_type=target_type, source_sampled=0,
            pairs_above_threshold=0, isolated_source_profiles=0,
        )

    with patch.object(service, "_corridor_density", new=_fake_corridor):
        await service.get_match_density(_cfg(), sample_limit=99999)

    assert calls == [service._MAX_SAMPLE_LIMIT]
