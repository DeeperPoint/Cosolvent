"""Unit tests for the Loop-3 consent engine + evidence grading (pure logic)."""

from app.modules.deals import story
from app.modules.deals.composer import grade_evidence

PROTECTED = ["price", "margin", "utilization", "floor"]


def _resp(uid, rtype, params, ts="2026-01-01T00:00:00+00:00"):
    return {"user_id": uid, "type": rtype, "created_at": ts, "payload": {"params": params}}


def test_accumulate_snapshot_latest_wins():
    responses = [
        _resp("u1", "annotate", [{"key": "rate", "value": "200", "unit": "CAD/hr"}], "2026-01-01T00:00:00+00:00"),
        _resp("u2", "correct", [{"key": "rate", "value": "215", "unit": "CAD/hr"}], "2026-01-02T00:00:00+00:00"),
        _resp("u1", "acknowledge", [], "2026-01-03T00:00:00+00:00"),
    ]
    snap = story.accumulate_snapshot(responses)
    assert snap["rate"]["value"] == "215"  # latest correction wins


def test_attribute_owners_last_contributor():
    responses = [
        _resp("u1", "annotate", [{"key": "price_floor", "value": "180"}], "2026-01-01T00:00:00+00:00"),
        _resp("u2", "annotate", [{"key": "scope", "value": "5-axis"}], "2026-01-02T00:00:00+00:00"),
    ]
    owners = story.attribute_owners(responses)
    assert owners["price_floor"] == "u1"
    assert owners["scope"] == "u2"


def test_is_protected_key_substring():
    assert story.is_protected_key("price_floor", PROTECTED)
    assert story.is_protected_key("shift_utilization", PROTECTED)
    assert not story.is_protected_key("delivery_window", PROTECTED)


def test_gate_redacts_protected_without_consent():
    snapshot = {
        "scope": {"label": "Scope", "value": "5-axis Ti"},
        "price_floor": {"label": "Price floor", "value": "180", "unit": "CAD/hr"},
    }
    owners = {"price_floor": "u1", "scope": "u2"}
    published, withheld = story.gate_snapshot(snapshot, owners, [], PROTECTED, "named")
    assert published["scope"]["value"] == "5-axis Ti"          # non-protected passes
    assert published["price_floor"]["value"] is None            # protected redacted
    assert published["price_floor"]["withheld"] is True
    assert [w["key"] for w in withheld] == ["price_floor"]


def test_gate_includes_protected_after_owner_consent():
    snapshot = {"price_floor": {"label": "Price floor", "value": "180"}}
    owners = {"price_floor": "u1"}
    consents = [{"scope": "attribute", "target": "price_floor", "user_id": "u1", "level": "named"}]
    published, withheld = story.gate_snapshot(snapshot, owners, consents, PROTECTED, "named")
    assert published["price_floor"]["value"] == "180"
    assert withheld == []


def test_attribute_consent_is_level_scoped():
    consents = [{"scope": "attribute", "target": "price_floor", "user_id": "u1", "level": "named"}]
    # consented at 'named' → not valid at the wider 'deal_context' audience (must re-consent)
    assert story.attribute_consented("price_floor", "u1", consents, "named")
    assert not story.attribute_consented("price_floor", "u1", consents, "deal_context")


def test_grade_evidence_excludes_withheld_and_tier_c():
    snapshot = {
        "rate": {"label": "Rate", "value": "215", "unit": "CAD/hr"},
        "price_floor": {"label": "Price floor", "value": None, "withheld": True},
    }
    ev = grade_evidence(snapshot, market_context="Comparable work runs $185-280/hr.")
    assert any("Rate: 215" in a for a in ev["tier_a"])          # Tier A present
    assert all("Price floor" not in a for a in ev["tier_a"])    # withheld excluded
    assert ev["tier_b"].startswith("Comparable")                # Tier B market context
    assert ev["tier_c_excluded"] is True                        # speculation excluded by design
