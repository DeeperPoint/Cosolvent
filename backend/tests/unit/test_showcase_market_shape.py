"""The public market-shape read: what an anonymous visitor learns about a market.

A Mode 1 visitor has no session, so the shape of the market has to arrive from
somewhere public or the client cannot tell a supply type from a demand one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.marketplace_config import load_marketplace_config
from app.modules.showcase.router import market_shape

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand, recruiter=facilitator
    return load_marketplace_config(FIXTURES / "talent.yaml")


@pytest.mark.asyncio
async def test_every_participant_type_reports_its_role_kind():
    body = await market_shape(config=_cfg())
    kinds = {t["slug"]: t["role_kind"] for t in body["participant_types"]}
    assert kinds["candidate"] == "supply"
    assert kinds["employer"] == "demand"
    assert kinds["recruiter"] == "facilitator"


@pytest.mark.asyncio
async def test_field_definitions_travel_with_each_type():
    body = await market_shape(config=_cfg())
    candidate = next(t for t in body["participant_types"] if t["slug"] == "candidate")
    cfg = _cfg()

    expected = {f.name for f in cfg.profile_schemas["candidate"].all_fields}
    assert {f["name"] for f in candidate["fields"]} == expected

    for field in candidate["fields"]:
        assert field["label"]
        assert field["type"]
        assert isinstance(field["required"], bool)


@pytest.mark.asyncio
async def test_options_are_listed_for_enum_fields_and_omitted_otherwise():
    body = await market_shape(config=_cfg())
    fields = [f for t in body["participant_types"] for f in t["fields"]]

    with_options = [f for f in fields if f["options"]]
    assert with_options, "the talent market defines enum fields"
    for field in with_options:
        assert all(isinstance(o, str) for o in field["options"])

    # A free-text field reports None rather than an empty list, so a client can
    # test truthiness without distinguishing the two.
    assert all(f["options"] is None or f["options"] for f in fields)


@pytest.mark.asyncio
async def test_searchability_is_reported_from_discovery_config():
    cfg = _cfg()
    searchable = set(cfg.discovery.searchable_types or [])
    body = await market_shape(config=cfg)
    for t in body["participant_types"]:
        assert t["searchable"] is (t["slug"] in searchable)


@pytest.mark.asyncio
async def test_each_type_reports_what_its_role_may_do():
    """Who may search and who may be found are different settings. A client that
    conflates them offers a search button to a role the backend will refuse."""
    cfg = _cfg()
    body = await market_shape(config=cfg)
    by_slug = {t["slug"]: t for t in body["participant_types"]}

    for pt in cfg.participant_types:
        reported = by_slug[pt.slug]["permissions"]
        assert reported["can_search"] is pt.permissions.can_search
        assert reported["visible_in_search"] is pt.permissions.visible_in_search

    # The two are genuinely independent, not aliases of one another.
    assert any(t["permissions"]["can_search"] is not t["searchable"]
               for t in body["participant_types"])


@pytest.mark.asyncio
async def test_the_market_names_itself():
    cfg = _cfg()
    body = await market_shape(config=cfg)
    assert body["marketplace"] == cfg.marketplace.name
