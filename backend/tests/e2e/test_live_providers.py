"""Live-provider E2E checks for OpenAI/Resend-backed flows."""

from __future__ import annotations

import os

import pytest

from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    new_client,
    random_email,
    register_update_submit,
    signup_user,
    wait_for,
)

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ChangeMe123!"
USER_PASSWORD = "UserPass123!"


def _require_live_env() -> None:
    if os.getenv("RUN_LIVE_E2E") != "1":
        pytest.skip("RUN_LIVE_E2E=1 required")
    required = ["OPENAI_API_KEY", "RESEND_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Live-provider E2E skipped: missing env vars: {', '.join(missing)}")


@pytest.mark.e2e
@pytest.mark.live
@pytest.mark.asyncio
async def test_live_provider_pipeline():
    _require_live_env()
    base_url = get_base_url("E2E_BASE_URL")
    admin = new_client(base_url)
    producer = new_client(base_url)
    buyer = new_client(base_url)

    try:
        await bootstrap_or_login_admin(admin, ADMIN_EMAIL, ADMIN_PASSWORD)

        upload = await admin.post(
            "/api/ai/documents",
            json={"filename": "live-doc.txt", "content": "Durum wheat protein and moisture trade guide."},
        )
        upload.raise_for_status()
        doc_id = upload.json()["id"]

        async def fetch_doc():
            listing = await admin.get("/api/ai/documents")
            listing.raise_for_status()
            for doc in listing.json():
                if doc.get("id") == doc_id:
                    return doc
            return None

        doc = await wait_for(
            fetch_doc,
            lambda d: d is not None and d.get("status") == "INDEXED",
            timeout_seconds=120.0,
            interval_seconds=2.0,
        )
        assert doc["status"] == "INDEXED"

        buyer_auth = await signup_user(
            buyer,
            email=random_email("live-buyer"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )
        await register_update_submit(
            buyer,
            "buyer",
            {"org_name": "Live Buyer Inc", "country": "Canada", "business_type": "Mill"},
        )
        query = await buyer.post(
            "/api/ai/query",
            json={"query": "What protein range is good for bread flour?", "thread_id": None, "filters": None},
        )
        query.raise_for_status()
        answer = query.json()
        assert answer.get("answer")
        assert answer.get("thread_id")

        await signup_user(
            producer,
            email=random_email("live-producer"),
            password=USER_PASSWORD,
            participant_type="producer",
        )
        await register_update_submit(
            producer,
            "producer",
            {"farm_name": "Live Valley", "country": "Canada", "primary_crops": ["Wheat"]},
        )
        apps = await admin.get("/api/admin/applications", params={"status": "pending"})
        apps.raise_for_status()
        app_id = apps.json()[0]["id"]
        approved = await admin.post(f"/api/admin/applications/{app_id}/approve")
        approved.raise_for_status()
        assert approved.json()["status"] == "approved"

        # keep variable used to avoid lint warning and ensure buyer remains authenticated
        assert buyer_auth.get("user_id")
    finally:
        await admin.aclose()
        await producer.aclose()
        await buyer.aclose()
