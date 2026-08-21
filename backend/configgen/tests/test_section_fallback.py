"""Tests for the domain-section discovery fallback.

extract.py's supply/demand profile projection used to be hardcoded to a section
literally named "goods" (matching grain_trade_schema.yaml's convention). A schema
that organizes its vocabulary under different section names (e.g. capacity/
material/quality — all equally valid; the synthesis prompt only suggests "goods"
as one example) used to silently produce an empty Offering/Requirements profile.
"""

from __future__ import annotations

from configgen.domain_schema import DomainSchema
from configgen.extract import extract_market


def test_domain_sections_detects_arbitrary_section_names():
    schema = DomainSchema({
        "vertical": "test_vertical",
        "capacity": {"description": "x", "fields": {"machine_type": {"type": "enum", "allowed_values": ["a", "b"]}}},
        "material": {"description": "x", "fields": {"grade": {"type": "enum", "allowed_values": ["x", "y"]}}},
        "participant_roles": {"supply": {}, "demand": {}},
    })
    assert schema.domain_sections() == ["capacity", "material"]


def test_domain_sections_excludes_reserved_top_level_keys():
    schema = DomainSchema({
        "schema_version": "1.0", "vertical": "v", "domain": "d",
        "source_authority": "x", "governing_law": "y",
        "participant_roles": {"supply": {}, "demand": {}},
        "referenced_standards": [{"id": "x"}],
        "goods": {"description": "x", "fields": {"a": {"type": "enum", "allowed_values": ["1"]}}},
    })
    assert schema.domain_sections() == ["goods"]


def test_grain_style_schema_still_uses_goods_only():
    """Backward compatibility: a schema with a `goods` section uses only that
    section, even if other domain sections are also present (unchanged behavior)."""
    schema = DomainSchema({
        "vertical": "test_vertical",
        "goods": {"description": "x", "fields": {"commodity": {"type": "enum", "allowed_values": ["wheat"]}}},
        "quality": {"description": "x", "fields": {"grade": {"type": "enum", "allowed_values": ["premium"]}}},
        "participant_roles": {"supply": {"label": "Seller"}, "demand": {"label": "Buyer"}},
    })
    market = extract_market(schema)
    seller = next(p for p in market.participants if p.role == "supply")
    offering = next(s for s in seller.sections if s.name == "Offering")
    names = {f.name for f in offering.fields}
    assert "commodity" in names
    assert "grade" not in names  # "quality" section not projected — goods-only, unchanged


def test_schema_without_goods_projects_all_domain_sections():
    schema = DomainSchema({
        "vertical": "test_vertical",
        "capacity": {"description": "x", "fields": {"machine_type": {"type": "enum", "allowed_values": ["mill", "lathe"]}}},
        "material": {"description": "x", "fields": {"grade": {"type": "enum", "allowed_values": ["ti", "al"]}}},
        "participant_roles": {"supply": {"label": "Machine Shop"}, "demand": {"label": "Buyer"}},
    })
    market = extract_market(schema)
    shop = next(p for p in market.participants if p.role == "supply")
    offering = next(s for s in shop.sections if s.name == "Offering")
    names = {f.name for f in offering.fields}
    assert names >= {"machine_type", "grade"}

    buyer = next(p for p in market.participants if p.role == "demand")
    requirements = next(s for s in buyer.sections if s.name == "Requirements")
    assert {f.name for f in requirements.fields} >= {"machine_type", "grade"}
