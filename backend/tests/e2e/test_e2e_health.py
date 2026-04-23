"""E2E: /api/health liveness endpoint."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_returns_status_and_marketplace(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "marketplace" in body
