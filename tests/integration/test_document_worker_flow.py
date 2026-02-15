"""Integration test for queue-backed document processing lifecycle."""

from __future__ import annotations

import pytest

from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    new_client,
    require_mode,
    wait_for,
)

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ChangeMe123!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_document_upload_is_processed_by_worker():
    require_mode("RUN_INTEGRATION")
    base_url = get_base_url("INTEGRATION_BASE_URL")
    admin = new_client(base_url)

    try:
        await bootstrap_or_login_admin(admin, ADMIN_EMAIL, ADMIN_PASSWORD)

        upload = await admin.post(
            "/api/ai/documents",
            json={"filename": "doc.txt", "content": "Marketplace operations and wheat protein specs."},
        )
        upload.raise_for_status()
        doc_id = upload.json()["id"]

        async def fetch_doc():
            listing = await admin.get("/api/ai/documents")
            listing.raise_for_status()
            docs = listing.json()
            for doc in docs:
                if doc.get("id") == doc_id:
                    return doc
            return None

        final_doc = await wait_for(
            fetch_doc,
            lambda d: d is not None and d.get("status") in {"INDEXED", "FAILED"},
            timeout_seconds=45.0,
            interval_seconds=1.0,
        )
        assert final_doc["status"] == "INDEXED"
    finally:
        await admin.aclose()
