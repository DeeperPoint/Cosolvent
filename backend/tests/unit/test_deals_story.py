"""Unit tests for the Story Progression System pure logic (GAP-4/5/15).

These exercise the DB-free core: content hashing, template completeness, milestone
derivation, dormancy, supersession, snapshot merge, disclosure ladder, and consent
gating. The DB-touching service/router paths are covered by integration tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.marketplace_config import _default_deal_instruments
from app.modules.deals import story
from app.modules.deals.hashing import content_hash
from app.modules.deals.templates import validate_snapshot

WINDOW = timedelta(days=14)
NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)


def _version(hash_="h1", required=("a", "b"), seq=1, state="published", published_at=None):
    return {
        "content_hash": hash_,
        "required_acknowledgers": list(required),
        "seq": seq,
        "state": state,
        "published_at": (published_at or NOW).isoformat(),
    }


def _resp(user, type_, hash_="h1"):
    return {"user_id": user, "type": type_, "content_hash": hash_}


# ── hashing ──────────────────────────────────────────────────────────────────
def test_content_hash_is_deterministic_and_order_independent():
    a = content_hash("anonymous", "story", {"x": {"value": 1}, "y": {"value": 2}})
    b = content_hash("anonymous", "story", {"y": {"value": 2}, "x": {"value": 1}})
    assert a == b


def test_content_hash_changes_with_content():
    base = content_hash("anonymous", "story", {"x": {"value": 1}})
    assert base != content_hash("named", "story", {"x": {"value": 1}})       # level
    assert base != content_hash("anonymous", "story2", {"x": {"value": 1}})  # narrative
    assert base != content_hash("anonymous", "story", {"x": {"value": 2}})   # snapshot


# ── template completeness (GAP-5) ──────────────────────────────────────────────
def test_template_incomplete_without_instrument():
    r = validate_snapshot({"parties": {"value": "x"}}, None, ["instrument", "parties"])
    assert not r.complete and r.missing == ["instrument", "parties"]


def test_template_missing_and_complete():
    req = ["instrument", "parties", "rate"]
    partial = {"instrument": {"value": "capacity_rental"}, "parties": {"value": "A,B"}}
    r = validate_snapshot(partial, "capacity_rental", req)
    assert not r.complete and r.missing == ["rate"]

    partial["rate"] = {"value": "200", "unit": "CAD/hr"}
    r2 = validate_snapshot(partial, "capacity_rental", req)
    assert r2.complete and r2.missing == []


def test_template_empty_string_is_not_present():
    r = validate_snapshot({"rate": {"value": "  "}}, "x", ["rate"])
    assert not r.complete


# ── GAP-15: the loan-like instruments exist in the baseline vocabulary ──────────
def test_default_instruments_include_gap15_vocabulary():
    names = {i.name for i in _default_deal_instruments()}
    assert {"capacity_rental", "reciprocity_preference"} <= names
    cap = next(i for i in _default_deal_instruments() if i.name == "capacity_rental")
    assert "operator_included" in cap.required_fields


# ── milestone derivation (integrity rule 3) ─────────────────────────────────────
def test_published_until_all_required_acknowledge():
    v = _version(required=("a", "b"))
    responses = [_resp("a", "acknowledge")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.PUBLISHED


def test_milestone_when_all_required_acknowledge():
    v = _version(required=("a", "b"))
    responses = [_resp("a", "acknowledge"), _resp("b", "acknowledge")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.MILESTONE


def test_annotate_counts_toward_milestone():
    v = _version(required=("a", "b"))
    responses = [_resp("a", "acknowledge"), _resp("b", "annotate")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.MILESTONE


def test_correction_blocks_even_if_others_acknowledged():
    v = _version(required=("a", "b"))
    responses = [_resp("a", "acknowledge"), _resp("b", "correct")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.BLOCKED


def test_hash_pinning_ignores_stale_acknowledgments():
    v = _version(hash_="h2", required=("a", "b"))
    # acknowledgments pinned to an old hash do not count
    responses = [_resp("a", "acknowledge", "h1"), _resp("b", "acknowledge", "h1")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.PUBLISHED


def test_stale_after_window_but_revivable_state_not_terminal():
    old = NOW - timedelta(days=20)
    v = _version(required=("a", "b"), published_at=old)
    assert story.compute_version_state(v, [], now=NOW, window=WINDOW) == story.STALE


def test_superseded_stays_superseded():
    v = _version(state=story.SUPERSEDED)
    responses = [_resp("a", "acknowledge"), _resp("b", "acknowledge")]
    assert story.compute_version_state(v, responses, now=NOW, window=WINDOW) == story.SUPERSEDED


def test_pending_acknowledgers():
    v = _version(required=("a", "b", "c"))
    responses = [_resp("a", "acknowledge")]
    assert story.pending_acknowledgers(v, responses) == ["b", "c"]


# ── snapshot merge (immutability preserved) ─────────────────────────────────────
def test_merge_snapshot_does_not_mutate_base():
    base = {"rate": {"label": "Rate", "value": "100"}}
    merged = story.merge_snapshot(base, [{"key": "rate", "value": "200"}, {"key": "scope", "value": "5-axis"}])
    assert base["rate"]["value"] == "100"          # base untouched
    assert merged["rate"]["value"] == "200"         # override applied
    assert merged["scope"]["value"] == "5-axis"     # new key added
    assert merged["scope"]["label"] == "scope"      # label defaulted


# ── disclosure ladder + consent gating (GAP-6) ──────────────────────────────────
def test_next_disclosure_level():
    levels = ["anonymous", "named", "deal_context"]
    assert story.next_disclosure_level("anonymous", levels) == "named"
    assert story.next_disclosure_level("named", levels) == "deal_context"
    assert story.next_disclosure_level("deal_context", levels) is None


def _deal_two_principals():
    return {
        "parties": [
            {"user_id": "a", "role": "principal", "status": "active", "exited_seq": None},
            {"user_id": "b", "role": "principal", "status": "active", "exited_seq": None},
        ]
    }


def test_reveal_requires_all_principals():
    deal = _deal_two_principals()
    consents = [{"user_id": "a", "scope": "disclosure_advance", "target": "named"}]
    assert not story.all_principals_consented(deal, consents, scope="disclosure_advance", target="named")
    consents.append({"user_id": "b", "scope": "disclosure_advance", "target": "named"})
    assert story.all_principals_consented(deal, consents, scope="disclosure_advance", target="named")


def test_pending_facilitator_is_not_an_active_party_for_gating():
    deal = _deal_two_principals()
    deal["parties"].append(
        {"user_id": "f", "role": "facilitator", "status": "pending_audience_consent", "exited_seq": None}
    )
    assert "f" not in story.active_party_ids(deal)
    assert story.principal_ids(deal) == ["a", "b"]
    # audience-expansion consent from both principals is required to admit f
    consents = [
        {"user_id": "a", "scope": "audience_expansion", "target": "f"},
        {"user_id": "b", "scope": "audience_expansion", "target": "f"},
    ]
    assert story.all_principals_consented(deal, consents, scope="audience_expansion", target="f")
