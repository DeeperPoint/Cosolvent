"""Golden + unit tests for the marketplace.yaml generator.

Run from the backend dir:  .venv/bin/python -m pytest configgen/tests -v
These tests are fully offline (no LLM).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.marketplace_config import MarketplaceConfig

from configgen.assemble import assemble
from configgen.domain_schema import DomainSchema
from configgen.extract import extract_market
from configgen.generate import generate_from_schema
from configgen.llm import make_llm_repair
from configgen.validate import ConfigValidationError, validate_and_repair

# CommonContext is a sibling repo of Cosolvent under the workspace root.
GRAIN_SCHEMA = (
    Path(__file__).resolve().parents[4] / "CommonContext" / "schemas" / "grain_trade_schema.yaml"
)


@pytest.fixture
def grain_schema_path() -> Path:
    if not GRAIN_SCHEMA.exists():
        pytest.skip(f"grain schema not found at {GRAIN_SCHEMA}")
    return GRAIN_SCHEMA


# ── Golden: grain schema -> valid, compilable config ──────────────────────

def test_grain_generates_valid_config(grain_schema_path):
    result = generate_from_schema(grain_schema_path)
    assert isinstance(result.config, MarketplaceConfig)
    slugs = result.config.type_slugs()
    # GAFTA grain has supply/demand/facilitator -> exactly 3 types (MVP cap).
    assert len(slugs) == 3
    assert set(r.role for r in result.config.participant_types) == {"supply", "demand", "facilitator"}


def test_grain_collapses_facilitator_subtypes(grain_schema_path):
    result = generate_from_schema(grain_schema_path)
    fac = next(p for p in result.market.participants if p.role == "facilitator")
    # The grain schema lists 9 facilitator subtypes; the MVP cap collapses them into one.
    assert len(fac.collapsed_subtypes) >= 5
    assert "broker" in fac.collapsed_subtypes


def test_emitted_yaml_roundtrips_through_validator(grain_schema_path, tmp_path):
    result = generate_from_schema(grain_schema_path)
    out = tmp_path / "marketplace.yaml"
    out.write_text(result.to_yaml())
    # Re-parse from disk exactly like Cosolvent does at startup.
    import yaml
    reloaded = MarketplaceConfig(**yaml.safe_load(out.read_text()))
    assert reloaded.type_slugs() == result.config.type_slugs()


def test_options_present_for_select_fields(grain_schema_path):
    result = generate_from_schema(grain_schema_path)
    for schema in result.config.profile_schemas.values():
        for f in schema.all_fields:
            if f.type in ("select", "multi_select"):
                assert f.options, f"{f.name} missing options"


def test_provenance_links_fields_to_schema(grain_schema_path):
    result = generate_from_schema(grain_schema_path)
    # products_offered should trace back to goods.commodity_type.
    assert any("commodity_type" in src for src in result.provenance.values())


# ── Pivot / extraction units ──────────────────────────────────────────────

def test_min_two_types_when_no_participant_roles():
    schema = DomainSchema({"vertical": "widgets"})  # no participant_roles
    market = extract_market(schema)
    assert len(market.participants) >= 2
    cfg = validate_and_repair(assemble(market))
    assert isinstance(cfg, MarketplaceConfig)


# ── Validate-repair loop ───────────────────────────────────────────────────

def test_deterministic_repair_drops_unknown_filter_field():
    schema = DomainSchema({"vertical": "widgets", "participant_roles": {"supply": {}, "demand": {}}})
    draft = assemble(extract_market(schema))
    draft["discovery"]["filter_fields"].append("does_not_exist")
    draft["discovery"]["searchable_types"].append("buyer")  # buyer is demand -> not visible_in_search
    cfg = validate_and_repair(draft)  # no LLM; deterministic repairs must handle both
    assert "does_not_exist" not in cfg.discovery.filter_fields
    assert "buyer" not in cfg.discovery.searchable_types


def test_llm_repair_callable_with_stub_client():
    """The repair hook is pluggable: a stub client stands in for OpenRouter."""

    class StubClient:
        def __init__(self, fixed):
            self.fixed = fixed
            self.calls = 0

        def complete(self, system, user):
            self.calls += 1
            import json
            return "```json\n" + json.dumps(self.fixed) + "\n```"

    # Build a valid baseline, then break it in a way deterministic repair won't touch
    # (an invalid field type), and have the stub "fix" it.
    schema = DomainSchema({"vertical": "widgets", "participant_roles": {"supply": {}, "demand": {}}})
    good = assemble(extract_market(schema))
    cfg_ok = validate_and_repair(dict(good))  # sanity: baseline is valid

    broken = MarketplaceConfig(**good).model_dump(mode="json")
    broken["profile_schemas"]["seller"]["sections"][0]["fields"][0]["type"] = "bogus_type"

    stub = StubClient(fixed=cfg_ok.model_dump(mode="json"))
    repaired = validate_and_repair(broken, llm_repair=make_llm_repair(stub))
    assert isinstance(repaired, MarketplaceConfig)
    assert stub.calls >= 1


def test_enrichment_applies_whitelisted_adjustments_only():
    """A stub LLM returns adjustments; only visibility/type-swap/label are applied,
    and attempts to touch options/name are ignored."""
    import json

    from configgen.assemble import assemble
    from configgen.enrich import enrich_fields

    schema = DomainSchema({
        "vertical": "widgets",
        "participant_roles": {"supply": {}, "demand": {}},
        "goods": {"fields": {
            "category": {"allowed_values": ["A", "B"], "required": True},
            "average_unit_price_usd": {"type": "number"},
        }},
    })
    draft = assemble(extract_market(schema))

    class StubClient:
        def complete(self, system, user):
            return json.dumps([
                # legit: make price protected, relabel it, switch category to single-select
                {"participant": "seller", "name": "average_unit_price_usd",
                 "visibility": "protected", "label": "Average Unit Price (USD)"},
                {"participant": "seller", "name": "category", "type": "select"},
                # illegal: try to change options + rename -> must be ignored
                {"participant": "seller", "name": "category", "options": ["HACKED"]},
            ])

    enriched = enrich_fields(StubClient(), draft)
    seller_fields = {f["name"]: f for s in enriched["profile_schemas"]["seller"]["sections"]
                     for f in s["fields"]}
    assert seller_fields["average_unit_price_usd"]["visibility"] == "protected"
    assert seller_fields["average_unit_price_usd"]["label"] == "Average Unit Price (USD)"
    assert seller_fields["category"]["type"] == "select"
    assert seller_fields["category"]["options"] == ["A", "B"]  # options untouched

    # And the enriched draft still validates.
    cfg = validate_and_repair(enriched)
    assert isinstance(cfg, MarketplaceConfig)


def test_unrepairable_raises():
    schema = DomainSchema({"vertical": "widgets", "participant_roles": {"supply": {}, "demand": {}}})
    draft = assemble(extract_market(schema))
    draft["profile_schemas"]["seller"]["sections"][0]["fields"][0]["type"] = "bogus_type"
    with pytest.raises(ConfigValidationError):
        validate_and_repair(draft)  # no LLM, deterministic repair can't fix a bad type
