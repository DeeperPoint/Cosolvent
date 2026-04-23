"""E2E: /api/notifications."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_notifications_require_auth(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/notifications")
    assert r.status_code == 401

    r_mark = await anonymous_client.put(
        "/api/notifications/00000000-0000-0000-0000-000000000000/read"
    )
    assert r_mark.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_notifications_returns_list(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.get("/api/notifications")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_notifications_accepts_pagination(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.get("/api/notifications", params={"skip": 0, "limit": 5})
    assert r.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mark_read_missing_notification_is_tolerant(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.put(
        "/api/notifications/00000000-0000-0000-0000-000000000000/read"
    )
    assert r.status_code in (200, 404)  # idempotent or explicit-not-found
