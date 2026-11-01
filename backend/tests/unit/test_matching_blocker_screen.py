"""Tests for GAP-18b: the symmetric blocker screen.

A plain HardGate only ever looks at the candidate's fields. Some marketplaces need a
pre-gate that looks at BOTH sides -- e.g. a worker's own undisclosed-record flag and an
employer's own blocking-criteria flag -- where either side tripping it means no proposal,
and neither side can tell afterward which of them (if either) was the reason. That is
BlockerRule / MatchProfile.blocker_screen, checked in matching.suggested_matches before
hard_gates or scoring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.marketplace_config import (
    BlockerRule,
    MarketplaceConfig,
    MatchingConfig,
    MatchProfile,
    MatchSlot,
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


# ── the pure helper ──────────────────────────────────────────────────────

def test_blocked_by_screen_checks_both_sides():
    rules = [BlockerRule(name="b", field="has_blocker", blocks_value=True)]
    assert matching._blocked_by_screen({"has_blocker": True}, {}, rules) is True
    assert matching._blocked_by_screen({}, {"has_blocker": True}, rules) is True
    assert matching._blocked_by_screen({}, {}, rules) is False


# ── end-to-end via suggested_matches ─────────────────────────────────────

@pytest.mark.asyncio
async def test_candidate_side_blocker_excludes_silently():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        blocker_screen=[BlockerRule(name="screen", field="blocked", blocks_value=True)],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("buyer-a", score=0.99, fields={"country": "Canada", "blocked": True}),
        _buyer_candidate("buyer-b", score=0.10, fields={"country": "Canada"}),
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    # buyer-a would otherwise rank first (0.99 vector score) -- the blocker must
    # exclude it from BOTH results and gated, not just rank it last or flag it.
    assert [r["id"] for r in out["results"]] == ["buyer-b"]
    assert out["gated"] == []
    assert out["total"] == 1


@pytest.mark.asyncio
async def test_viewer_side_blocker_excludes_every_candidate():
    """The symmetry this feature exists for: the VIEWER's own field can block a
    match too, even though a plain HardGate can never see the viewer's side."""
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        blocker_screen=[BlockerRule(name="screen", field="blocked", blocks_value=True)],
    )
    cfg = _config_with_matching(profile)
    candidates = [_buyer_candidate("buyer-a", score=0.99, fields={"country": "Canada"})]
    with patch.object(matching.profiles_repo, "get_profile_by_id",
                       new=AsyncMock(return_value=_producer_profile({"blocked": True}))), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    assert out["results"] == []
    assert out["gated"] == []
    assert out["total"] == 0


def test_config_rejects_unknown_blocker_field():
    # MarketplaceConfig's field-existence check is a model_validator(mode="after") on
    # MarketplaceConfig itself, so it only fires at construction -- re-validate via
    # model_validate() after mutating .discovery.matching, same as the CLI's `validate`
    # command does on load, rather than relying on attribute-assignment validation.
    cfg = _config_with_matching(MatchProfile(
        vector_weight=1.0,
        blocker_screen=[BlockerRule(name="screen", field="not_a_real_field")],
    ))
    with pytest.raises(Exception, match="blocker_screen.*unknown field"):
        MarketplaceConfig.model_validate(cfg.model_dump())
