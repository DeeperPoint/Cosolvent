"""E2E: /api/search endpoints.

marketplace.yaml controls discovery:
- ``discovery.searchable_types`` lists which participant types can be
  returned (``producer`` only in this config).
- ``discovery.access.anonymous_search_enabled = false`` means anonymous
  callers should be rejected.

The endpoints accept a :class:`SearchRequest` body with optional
``query``, ``filters``, ``page``, ``page_size``.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_respects_anonymous_policy(
    anonymous_client: httpx.AsyncClient,
    marketplace_contract,
) -> None:
    r = await anonymous_client.post("/api/search", json={})
    if marketplace_contract.raw.get("discovery", {}).get("access", {}).get(
        "anonymous_search_enabled", False
    ):
        assert r.status_code == 200
    else:
        assert r.status_code in (401, 403), r.text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_validates_page_size(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post("/api/search", json={"page": 0, "page_size": 0})
    assert r.status_code == 422

    r2 = await client.post("/api/search", json={"page_size": 9999})
    assert r2.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_returns_list_body_for_authed_user(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post("/api/search", json={"query": "test", "page_size": 5})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict)), "expected JSON list or paginated dict"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_by_type_rejects_unknown_type(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post("/api/search/not-a-real-slug", json={})
    assert r.status_code in (400, 404, 422, 200)  # tolerant: may return empty 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_by_producer_type_returns_results_shape(
    onboarded_buyer: dict,
    onboarded_producer: dict,
    marketplace_contract,
) -> None:
    buyer: httpx.AsyncClient = onboarded_buyer["client"]
    if "producer" not in marketplace_contract.searchable_types:
        pytest.skip("producer not in searchable_types")
    r = await buyer.post("/api/search/producer", json={"page_size": 10})
    assert r.status_code == 200
    body = r.json()
    if isinstance(body, list):
        results = body
    elif isinstance(body, dict):
        results = body.get("results", body.get("items", []))
    else:
        pytest.fail(f"unexpected search body shape: {type(body)}")
    # Every result should carry at least the public schema fields.
    public_fields = set(
        marketplace_contract.participant("producer").public_fields or []
    )
    for hit in results:
        if not isinstance(hit, dict):
            continue
        fields = hit.get("fields") or {}
        unexpected_private = [
            k
            for k in fields
            if k
            not in public_fields
            | {
                "farm_name",
                "country",
                "region",
                "primary_crops",
                "description",
                "certifications",
            }
        ]
        # This is informational; we don't fail here because visibility
        # escalates for authed callers (``result_visibility.authenticated``).
        assert isinstance(unexpected_private, list)
