"""HTTP surface for population ingest (GAP-10 / GAP-9).

The CLI is the documented path for a real load; this router exists so an operator
can exercise the ingest boundary from `/docs`. These tests assert the routes
behave identically to the service — in particular that the watermark gate and the
production cutover are enforced through HTTP too, not just via the CLI.

Gated by RUN_INTEGRATION (needs a live migrated database).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import close_db, connect_db, get_collection
from app.core.dependencies import require_admin
from app.main import create_app
from tests.e2e.helpers import require_mode

POPULATION_FILE = Path(__file__).parent.parent / "fixtures" / "clientsynth_population.json"
SECRET = "e2e-shared-secret"


def _records() -> list[dict]:
    return json.loads(POPULATION_FILE.read_text(encoding="utf-8"))["records"]


async def _purge(records: list[dict]) -> None:
    for r in records:
        await get_collection("profiles").delete_one({"external_id": r["external_id"]})
        await get_collection("users").delete_one({"external_id": r["external_id"]})


@pytest.fixture
def app():
    application = create_app()
    # The routes are admin-only; auth itself is covered by the auth suite.
    application.dependency_overrides[require_admin] = lambda: {"_id": "admin", "role": "admin"}
    return application


@pytest.mark.integration
@pytest.mark.asyncio
async def test_population_router_enforces_the_boundary(app, monkeypatch):
    require_mode("RUN_INTEGRATION")
    # The router resolves the secret from settings, which is instantiated at
    # import time — setting the environment variable here would be too late.
    monkeypatch.setattr(settings, "synthetic_watermark_secret", SECRET)

    records = _records()
    await connect_db()
    try:
        await _purge(records)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Empty to begin with.
            res = await client.get("/api/admin/population/count")
            assert res.status_code == 200
            baseline = res.json()["synthetic_profiles"]

            # A signed population loads.
            res = await client.post(
                "/api/admin/population/import",
                json={"records": records, "mode": "demo", "index": False},
            )
            assert res.status_code == 200
            body = res.json()
            assert body["loaded"] == len(records)
            assert body["rejected_watermark"] == 0
            assert body["skipped_invalid"] == 0

            # Re-import upserts rather than duplicating.
            res = await client.post(
                "/api/admin/population/import",
                json={"records": records, "mode": "demo", "index": False},
            )
            assert res.json()["loaded"] == 0
            assert res.json()["updated"] == len(records)

            # Production refuses synthetic data — the clean cutover.
            res = await client.post(
                "/api/admin/population/import",
                json={"records": records, "mode": "production", "index": False},
            )
            assert res.json()["rejected_watermark"] == len(records)

            # Demo requires the watermark.
            stripped = [{k: v for k, v in r.items() if k != "_watermark"} for r in records]
            res = await client.post(
                "/api/admin/population/import",
                json={"records": stripped, "mode": "demo", "index": False},
            )
            assert res.json()["rejected_watermark"] == len(records)
            assert res.json()["loaded"] == 0

            # Tampering with a signed field is caught.
            tampered = json.loads(json.dumps(records))
            tampered[0]["fields"]["farm_name"] = "ATTACKER INJECTED FARM"
            res = await client.post(
                "/api/admin/population/import",
                json={"records": tampered, "mode": "demo", "index": False},
            )
            assert res.json()["rejected_watermark"] == 1

            # The file upload path accepts the same artifact the CLI consumes.
            res = await client.post(
                "/api/admin/population/import-file?mode=demo&index=false",
                files={"file": ("population.json", POPULATION_FILE.read_bytes(), "application/json")},
            )
            assert res.status_code == 200
            assert res.json()["updated"] == len(records)

            # Malformed input fails loudly rather than importing nothing quietly.
            res = await client.post(
                "/api/admin/population/import-file?mode=demo",
                files={"file": ("bad.json", b"not json at all", "application/json")},
            )
            assert res.status_code == 400
            assert "Invalid population file" in res.json()["detail"]

            # An empty request is rejected rather than reported as a success.
            res = await client.post(
                "/api/admin/population/import",
                json={"records": [], "mode": "demo", "index": False},
            )
            assert res.status_code == 400

            res = await client.get("/api/admin/population/count")
            assert res.json()["synthetic_profiles"] == baseline + len(records)
    finally:
        await _purge(records)
        await close_db()
