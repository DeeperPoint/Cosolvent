"""Tests for GAP-18c: the additive, never-negative score modifier.

A plain MatchSlot is part of the weights-sum-to-1.0 budget, so giving a
dimension more weight necessarily takes weight from another. Some marketplaces
need a dimension that can only ever help -- e.g. "evidence support" in
DT-Indigenous-Job-Matching's implementation-plan.md §4.3: absence is zero, not
a penalty, and it never competes with the other weights. That is
ScoreModifier / MatchProfile.modifiers, applied after slot scoring and clamped
to 1.0.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.marketplace_config import (
    MarketplaceConfig,
    MatchingConfig,
    MatchProfile,
    MatchSlot,
    ScoreModifier,
    load_marketplace_config,
)
from app.modules.discovery import matching

FIXTURES = Path(__file__).parent.parent / "test_config"


def _config_with_matching(profile: MatchProfile) -> MarketplaceConfig:
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    cfg.discovery.matching = MatchingConfig(default=profile)
    return cfg


def _producer_profile(extra_fields: dict | None = None) -> dict:
    return {
        "_id": "p-1", "user_id": "u-1", "participant_type": "producer", "status": "active",
        "fields": {"country": "Canada", "primary_crops": ["Wheat"], **(extra_fields or {})},
    }


def _buyer_candidate(pid: str, score: float, fields: dict) -> dict:
    return {
        "id": pid, "score": score, "metadata": {"participant_type": "buyer"},
        "profile": {"_id": pid, "user_id": f"bu-{pid}", "participant_type": "buyer",
                    "status": "active", "fields": {"org_name": "Acme", **fields}},
    }


@pytest.mark.asyncio
async def test_modifier_adds_bonus_when_field_present():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        modifiers=[ScoreModifier(name="evidence", field="evidence_items", max_bonus=0.2)],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("with-evidence", score=0.0, fields={"country": "Canada", "evidence_items": ["letter"]}),
        _buyer_candidate("without-evidence", score=0.0, fields={"country": "Canada"}),
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    by_id = {r["id"]: r for r in out["results"]}
    # Both match the geo slot identically (country equal, weight 0.4) and have
    # zero vector score -- the only difference should be the modifier's bonus.
    assert by_id["with-evidence"]["score"] == pytest.approx(0.4 + 0.2)
    assert by_id["without-evidence"]["score"] == pytest.approx(0.4)
    assert by_id["with-evidence"]["score_breakdown"]["modifiers"]["evidence"] == {
        "applied": True, "bonus": 0.2,
    }
    assert by_id["without-evidence"]["score_breakdown"]["modifiers"]["evidence"] == {
        "applied": False, "bonus": 0.0,
    }


@pytest.mark.asyncio
async def test_modifier_never_reduces_score_and_clamps_at_one():
    profile = MatchProfile(
        vector_weight=1.0,
        modifiers=[ScoreModifier(name="evidence", field="evidence_items", max_bonus=0.5)],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("maxed", score=1.0, fields={"country": "Canada", "evidence_items": ["letter"]}),
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    # vector_weight(1.0)*1.0 + bonus(0.5) = 1.5, clamped to 1.0 -- never exceeds the scale.
    assert out["results"][0]["score"] == pytest.approx(1.0)


def test_config_rejects_unknown_modifier_field():
    cfg = _config_with_matching(MatchProfile(
        vector_weight=1.0,
        modifiers=[ScoreModifier(name="evidence", field="not_a_real_field", max_bonus=0.1)],
    ))
    with pytest.raises(Exception, match="modifier.*unknown field"):
        MarketplaceConfig.model_validate(cfg.model_dump())


def test_modifiers_excluded_from_weight_budget():
    # A modifier does not count toward the vector_weight + slot-weights == 1.0
    # invariant -- it sits outside that budget entirely.
    profile = MatchProfile(
        vector_weight=1.0,
        modifiers=[ScoreModifier(name="evidence", field="evidence_items", max_bonus=0.9)],
    )
    assert profile.vector_weight == 1.0
