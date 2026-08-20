"""Tests for GAP-3: config-driven weighted-slot scoring + hard gates.

Covers the pure comparator/gate helpers, the matching config validation, and the
config-driven path of suggested_matches (composite from weights, hard-gate
exclusion, and the score explanation). Repo + vector_service are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from pydantic import ValidationError

from app.core.marketplace_config import (
    HardGate,
    MarketplaceConfig,
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
        "fields": {"country": "Canada", "primary_crops": ["Wheat", "Barley"]},
    }


def _buyer_candidate(pid: str, score: float, fields: dict) -> dict:
    return {
        "id": pid, "score": score, "metadata": {"participant_type": "buyer"},
        "profile": {"_id": pid, "user_id": f"bu-{pid}", "participant_type": "buyer",
                    "status": "active", "fields": {"org_name": "Acme", **fields}},
    }


# ── comparator helpers ────────────────────────────────────────────────────

def test_pair_score_scalar_eq():
    assert matching._pair_score("scalar_eq", "Canada", "Canada") == 1.0
    assert matching._pair_score("scalar_eq", "Canada", "USA") == 0.0
    assert matching._pair_score("scalar_eq", None, "Canada") is None


def test_pair_score_jaccard():
    assert matching._pair_score("jaccard", ["a", "b"], ["a", "c"]) == pytest.approx(1 / 3)
    assert matching._pair_score("jaccard", "a", ["a", "b"]) == pytest.approx(0.5)


def test_pair_score_numeric_proximity():
    assert matching._pair_score("numeric_proximity", 100, 100) == 1.0
    assert matching._pair_score("numeric_proximity", 100, 50) == pytest.approx(0.5)
    assert matching._pair_score("numeric_proximity", 100, 0) == 0.0
    assert matching._pair_score("numeric_proximity", "x", 5) is None


def test_pair_score_window_overlap_identical_windows():
    a = ["2026-09-01", "2026-09-14"]
    assert matching._pair_score("window_overlap", a, list(a)) == 1.0


def test_pair_score_window_overlap_partial_overlap():
    # Union 2026-09-01..2026-09-20 (20 days), overlap 2026-09-10..2026-09-14 (5 days).
    a = ["2026-09-01", "2026-09-14"]
    b = ["2026-09-10", "2026-09-20"]
    assert matching._pair_score("window_overlap", a, b) == pytest.approx(5 / 20)


def test_pair_score_window_overlap_disjoint_windows():
    a = ["2026-09-01", "2026-09-05"]
    b = ["2026-09-10", "2026-09-14"]
    assert matching._pair_score("window_overlap", a, b) == 0.0


def test_pair_score_window_overlap_accepts_dict_form():
    a = {"start": "2026-09-01", "end": "2026-09-14"}
    b = {"start": "2026-09-01", "end": "2026-09-14"}
    assert matching._pair_score("window_overlap", a, b) == 1.0


def test_pair_score_window_overlap_none_when_unparseable():
    assert matching._pair_score("window_overlap", "not-a-window", ["2026-09-01", "2026-09-14"]) is None
    assert matching._pair_score("window_overlap", ["2026-09-14", "2026-09-01"], ["2026-09-01", "2026-09-14"]) is None  # start after end
    assert matching._pair_score("window_overlap", None, ["2026-09-01", "2026-09-14"]) is None


def test_slot_score_averages_present_fields():
    s = matching._slot_score("scalar_eq", {"a": "1", "b": "2"}, {"a": "1", "b": "9"}, ["a", "b"])
    assert s == pytest.approx(0.5)
    # no comparable fields -> 0.0
    assert matching._slot_score("scalar_eq", {"a": "1"}, {"b": "2"}, ["a", "b"]) == 0.0


# ── hard gates ────────────────────────────────────────────────────────────

def test_check_gate_operators():
    eq = HardGate(name="g", field="country", op="equals", value="Canada")
    assert matching._check_gate("Canada", eq)[0] is True
    assert matching._check_gate("USA", eq)[0] is False
    assert matching._check_gate(None, eq)[0] is False  # missing fails

    present = HardGate(name="g", field="cwi", op="present")
    assert matching._check_gate("yes", present)[0] is True
    assert matching._check_gate([], present)[0] is False

    in_ = HardGate(name="g", field="country", op="in", value=["Canada", "USA"])
    assert matching._check_gate("USA", in_)[0] is True
    assert matching._check_gate("Brazil", in_)[0] is False

    gte = HardGate(name="g", field="cap", op="gte", value=100)
    assert matching._check_gate(150, gte)[0] is True
    assert matching._check_gate(50, gte)[0] is False


def test_evaluate_gates_reports_reasons():
    gates = [HardGate(name="ca_only", field="country", op="equals", value="Canada")]
    res = matching._evaluate_gates({"country": "USA"}, gates)
    assert res[0]["passed"] is False
    assert "country" in res[0]["reason"]
    ok = matching._evaluate_gates({"country": "Canada"}, gates)
    assert ok[0]["passed"] is True and ok[0]["reason"] is None


# ── matching config validation ────────────────────────────────────────────

def test_match_profile_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        MatchProfile(vector_weight=0.5, slots=[MatchSlot(name="g", fields=["country"], weight=0.2)])
    # valid: 0.6 + 0.4 == 1.0
    MatchProfile(vector_weight=0.6, slots=[MatchSlot(name="g", fields=["country"], weight=0.4)])


def test_match_profile_rejects_duplicate_slot_names():
    with pytest.raises(ValidationError):
        MatchProfile(
            vector_weight=0.2,
            slots=[MatchSlot(name="g", fields=["a"], weight=0.4),
                   MatchSlot(name="g", fields=["b"], weight=0.4)],
        )


def test_matching_config_profile_for_prefers_per_target():
    default = MatchProfile(vector_weight=1.0)
    special = MatchProfile(vector_weight=0.5, slots=[MatchSlot(name="g", fields=["country"], weight=0.5)])
    mc = MatchingConfig(default=default, per_target={"buyer": special})
    assert mc.profile_for("buyer") is special
    assert mc.profile_for("facilitator") is default


def _agri_raw_with_matching(matching_block: dict) -> dict:
    raw = yaml.safe_load((FIXTURES / "agriculture.yaml").read_text())
    raw["discovery"]["matching"] = matching_block
    return raw


def test_cross_validate_rejects_unknown_matching_field():
    raw = _agri_raw_with_matching(
        {"default": {"vector_weight": 0.5, "slots": [{"name": "x", "fields": ["nope"], "weight": 0.5}]}}
    )
    with pytest.raises(ValueError, match="unknown field 'nope'"):
        MarketplaceConfig(**raw)


def test_cross_validate_rejects_unknown_per_target_type():
    raw = _agri_raw_with_matching({"per_target": {"ghost": {"vector_weight": 1.0}}})
    with pytest.raises(ValueError, match="unknown type 'ghost'"):
        MarketplaceConfig(**raw)


def test_cross_validate_accepts_valid_matching_block():
    raw = _agri_raw_with_matching(
        {"default": {
            "vector_weight": 0.6,
            "slots": [{"name": "geo", "fields": ["country"], "comparator": "scalar_eq", "weight": 0.4}],
            "hard_gates": [{"name": "ca", "field": "country", "op": "equals", "value": "Canada"}],
        }}
    )
    cfg = MarketplaceConfig(**raw)
    assert cfg.discovery.matching.default.vector_weight == 0.6


# ── config-driven suggested_matches ───────────────────────────────────────

def _config_with_matching(profile: MatchProfile) -> MarketplaceConfig:
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    cfg.discovery.matching = MatchingConfig(default=profile)
    return cfg


def _run(cfg, candidates):
    return matching.suggested_matches(
        cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"},
    ), candidates


@pytest.mark.asyncio
async def test_config_driven_composite_and_ranking():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("buyer-a", score=0.90, fields={"country": "USA"}),
        _buyer_candidate("buyer-b", score=0.60, fields={"country": "Canada"}),
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    # buyer-a: 0.6*0.90 + 0.4*0.0 = 0.54 ; buyer-b: 0.6*0.60 + 0.4*1.0 = 0.76
    assert [r["id"] for r in out["results"]] == ["buyer-b", "buyer-a"]
    assert out["results"][0]["score"] == pytest.approx(0.76)
    assert out["results"][1]["score"] == pytest.approx(0.54)
    bd = out["results"][0]["score_breakdown"]
    assert bd["vector_weight"] == 0.6
    assert bd["slots"]["geo"] == {"score": 1.0, "weight": 0.4}
    assert out["gated"] == []  # matching profile present -> gated key exists


@pytest.mark.asyncio
async def test_hard_gate_excludes_and_explains():
    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        hard_gates=[HardGate(name="ca_only", field="country", op="equals", value="Canada")],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("buyer-a", score=0.99, fields={"country": "USA"}),      # gated out
        _buyer_candidate("buyer-b", score=0.50, fields={"country": "Canada"}),   # passes
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)), \
         patch.object(matching, "active_escape_hatches", new=AsyncMock(return_value={})), \
         patch.object(matching, "maybe_record_gate_gap", new=AsyncMock()):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    # Highest vector score is gated out, so it must NOT appear in ranked results.
    assert [r["id"] for r in out["results"]] == ["buyer-b"]
    assert out["total"] == 1
    assert len(out["gated"]) == 1
    g = out["gated"][0]
    assert g["id"] == "buyer-a" and g["gated"] is True
    assert g["gate_failures"] == ["ca_only"]
    failed = [x for x in g["score_breakdown"]["gates"] if not x["passed"]]
    assert failed and "country" in failed[0]["reason"]


@pytest.mark.asyncio
async def test_config_driven_output_validates_against_response_model():
    # Guards the API contract: the config-driven shape (slots/gates/gated) must
    # pass the endpoint's response_model, which the legacy shape's required
    # field_overlap would otherwise reject.
    from app.modules.discovery.schemas import SuggestedMatchesResponse

    profile = MatchProfile(
        vector_weight=0.6,
        slots=[MatchSlot(name="geo", fields=["country"], comparator="scalar_eq", weight=0.4)],
        hard_gates=[HardGate(name="ca_only", field="country", op="equals", value="Canada")],
    )
    cfg = _config_with_matching(profile)
    candidates = [
        _buyer_candidate("buyer-a", score=0.99, fields={"country": "USA"}),
        _buyer_candidate("buyer-b", score=0.50, fields={"country": "Canada"}),
    ]
    with patch.object(matching.profiles_repo, "get_profile_by_id", new=AsyncMock(return_value=_producer_profile())), \
         patch.object(matching.vector_service, "get_profile_embedding", new=AsyncMock(return_value=[0.1] * 1536)), \
         patch.object(matching.vector_service, "find_similar_profiles", new=AsyncMock(return_value=candidates)), \
         patch.object(matching, "active_escape_hatches", new=AsyncMock(return_value={})), \
         patch.object(matching, "maybe_record_gate_gap", new=AsyncMock()):
        out = await matching.suggested_matches(
            cfg, profile_id="p-1", type_slug="producer", viewer={"_id": "u-1", "role": "user"})

    validated = SuggestedMatchesResponse(**out)
    assert validated.results[0].score_breakdown.slots["geo"].weight == 0.4
    assert validated.gated[0].gate_failures == ["ca_only"]
