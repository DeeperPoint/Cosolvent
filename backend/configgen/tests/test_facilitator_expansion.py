"""Tests for facilitator-subtype expansion (Cosolvent ROADMAP Conflict C3 —
resolved: MAX_PARTICIPANT_TYPES > 3, so configgen should use that headroom instead
of always collapsing facilitator subtypes into one type).

test_grain.py already covers the "still collapses when subtypes exceed the budget"
path (GAFTA's 9 subtypes > the 6-slot budget); these tests cover the new "expands
into one type per subtype" path plus the boundary.
"""

from __future__ import annotations

from app.core.marketplace_config import MAX_PARTICIPANT_TYPES

from configgen.domain_schema import DomainSchema
from configgen.extract import extract_market


def _schema(subtypes: list[dict]) -> DomainSchema:
    return DomainSchema({
        "vertical": "test_vertical",
        "participant_roles": {
            "supply": {"label": "Seller"},
            "demand": {"label": "Buyer"},
            "facilitator": {"label": "Provider", "subtypes": subtypes},
        },
    })


def test_facilitator_expands_into_separate_types_when_budget_allows():
    schema = _schema([
        {"role": "quality_inspector", "description": "Inspects parts"},
        {"role": "logistics_provider", "description": "Moves parts"},
    ])
    market = extract_market(schema)
    fac_types = [p for p in market.participants if p.role == "facilitator"]

    assert len(fac_types) == 2
    assert {p.slug for p in fac_types} == {"quality_inspector", "logistics_provider"}
    assert all(not p.collapsed_subtypes for p in fac_types)
    # Each subtype's description carries through as that participant type's own.
    inspector = next(p for p in fac_types if p.slug == "quality_inspector")
    assert inspector.description == "Inspects parts"


def test_expanded_facilitator_types_skip_the_redundant_services_offered_field():
    schema = _schema([{"role": "quality_inspector", "description": ""}])
    market = extract_market(schema)
    fac = next(p for p in market.participants if p.role == "facilitator")
    services_section = next(s for s in fac.sections if s.name == "Services")
    assert all(f.name != "services_offered" for f in services_section.fields)


def test_facilitator_still_collapses_when_subtypes_exceed_budget():
    # Budget = MAX_PARTICIPANT_TYPES - 2 (supply + demand); go one over it.
    budget = MAX_PARTICIPANT_TYPES - 2
    many_subtypes = [{"role": f"role_{i}", "description": ""} for i in range(budget + 1)]
    schema = _schema(many_subtypes)
    market = extract_market(schema)
    fac_types = [p for p in market.participants if p.role == "facilitator"]

    assert len(fac_types) == 1
    assert len(fac_types[0].collapsed_subtypes) == budget + 1
    assert len(market.participants) <= MAX_PARTICIPANT_TYPES + 1  # collapse, not truncation


def test_facilitator_collapses_when_no_subtypes_declared():
    schema = DomainSchema({
        "vertical": "test_vertical",
        "participant_roles": {
            "supply": {"label": "Seller"},
            "demand": {"label": "Buyer"},
            "facilitator": {"label": "Provider"},
        },
    })
    market = extract_market(schema)
    fac_types = [p for p in market.participants if p.role == "facilitator"]
    assert len(fac_types) == 1
    assert fac_types[0].slug == "provider"
