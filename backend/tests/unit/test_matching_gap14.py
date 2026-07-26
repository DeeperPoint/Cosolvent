"""Tests for GAP-14 (payoff half): escape hatches make hard gates conditional.

Covers the pure condition/unlock helpers and the config-driven path of
suggested_matches with active escape hatches — a candidate that fails a hard gate
but satisfies a hatch's alternative-compliance condition is *unlocked* (ranked, not
gated), and one blocked candidate emits a deduped Loop-2 pull signal.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.marketplace_config import (
    HardGate,
    MatchProfile,
    MatchSlot,
    MatchingConfig,
    load_marketplace_config,
)
from app.modules.discovery import matching

FIXTURES = Path(__file__).parent.parent / "test_config"


def _producer_profile() -> dict:
    return {
        "_id": "p-1", "user_id": "u-1", "participant_type": "producer", "status": "active",
        "fields": {"country": "Canada", "primary_crops": ["Wheat"]},
    }


def _buyer_candidate(pid: str, score: float, fields: dict) -> dict:
    return {
        "id": pid, "score": score, "metadata": {"participant_type": "buyer"},
        "profile": {"_id": pid, "user_id": f"bu-{pid}", "participant_type": "buyer",
                    "status": "active", "fields": {"org_name": "Acme", **fields}},
    }


# ── pure helpers ──────────────────────────────────────────────────────────

def test_condition_passes_reuses_gate_ops():
    assert matching._condition_passes({"cert": "W59-002"}, {"field": "cert", "op": "present"})
    assert not matching._condition_passes({}, {"field": "cert", "op": "present"})
    assert matching._condition_passes({"cap": 150}, {"field": "cap", "op": "gte", "value": 100})
    assert not matching._condition_passes({"cert": "x"}, {"field": "cert", "op": "equals", "value": "y"})
    # A malformed condition (no field) never passes.
    assert not matching._condition_passes({"cert": "x"}, {})


def test_evaluate_gates_unlocks_failed_gate_via_hatch():
    gates = [HardGate(name="ca_only", field="country", op="equals", value="Canada")]
    hatches = {"ca_only": [
        {"id": "h1", "rationale": "USMCA equivalence", "condition": {"field": "trade_bloc", "op": "equals", "value": "usmca"}}
    ]}
    # Candidate fails the gate (USA) but satisfies the hatch condition -> unlocked.
    res = matching._evaluate_gates({"country": "USA", "trade_bloc": "usmca"}, gates, hatches)
    assert res[0]["passed"] is True
    assert res[0]["unlocked"] is True
    assert res[0]["unlocked_by"]["rationale"] == "USMCA equivalence"
    assert res[0]["blocked_reason"] and "country" in res[0]["blocked_reason"]

    # Same failing gate, but the hatch condition is not met -> still blocked.
    res2 = matching._evaluate_gates({"country": "USA", "trade_bloc": "eu"}, gates, hatches)
    assert res2[0]["passed"] is False
    assert res2[0].get("unlocked") is not True


# ── config-driven suggested_matches with escape hatches ────────────────────

def _config_with_matching(profile: MatchProfile):
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    cfg.discovery.matching = MatchingConfig(default=profile)
    return cfg


@pytest.mark.asyncio
async def test_escape_hatch_unlocks_gated_candidate():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        hard_gates=[HardGate(name="ca_only", field="country", op="equals", value="Canada")],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        # USA fails ca_only, but carries the alternative-compliance flag the hatch checks.
        _buyer_candidate("buyer-a", score=0.99, fields={"country": "USA", "trade_bloc": "usmca"}),
        _buyer_candidate("buyer-b", score=0.50, fields={"country": "Canada"}),
    ]
    hatches = {"ca_only": [
        {"id": "h1", "rationale": "USMCA equivalence", "condition": {"field": "trade_bloc", "op": "equals", "value": "usmca"}}
    ]}
    gate_gap = AsyncMock()
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)), \
         patch.object(matching, "active_escape_hatches", new=AsyncMock(return_value=hatches)), \
         patch.object(matching, "maybe_record_gate_gap", new=gate_gap):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    # buyer-a is unlocked -> it appears in ranked results, not gated. (buyer-b outranks it
    # because its country matches the geo slot; ordering is not what this test asserts.)
    assert {r["id"] for r in out["results"]} == {"buyer-a", "buyer-b"}
    assert out["gated"] == []
    unlocked_a = next(r for r in out["results"] if r["id"] == "buyer-a")["unlocked_gates"]
    assert unlocked_a == [{"name": "ca_only", "rationale": "USMCA equivalence"}]
    # buyer-b passed the gate outright -> no unlocked_gates on it.
    assert next(r for r in out["results"] if r["id"] == "buyer-b").get("unlocked_gates") is None
    # No candidate is actually blocked -> no pull signal.
    gate_gap.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocked_gate_emits_deduped_pull_signal():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        hard_gates=[HardGate(name="ca_only", field="country", op="equals", value="Canada")],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("buyer-a", score=0.99, fields={"country": "USA"}),    # blocked, no hatch
        _buyer_candidate("buyer-b", score=0.90, fields={"country": "Brazil"}),  # blocked, no hatch
        _buyer_candidate("buyer-c", score=0.50, fields={"country": "Canada"}),  # passes
    ]
    gate_gap = AsyncMock()
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)), \
         patch.object(matching, "active_escape_hatches", new=AsyncMock(return_value={})), \
         patch.object(matching, "maybe_record_gate_gap", new=gate_gap):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    assert [r["id"] for r in out["results"]] == ["buyer-c"]
    assert {g["id"] for g in out["gated"]} == {"buyer-a", "buyer-b"}
    # Two candidates blocked by the SAME gate -> the pull signal is emitted once per gate.
    gate_gap.assert_awaited_once()
    assert gate_gap.await_args.kwargs["gate_name"] == "ca_only"
