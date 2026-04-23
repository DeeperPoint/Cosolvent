"""E2E: /api/ai/... endpoints.

Most AI endpoints require admin auth:
- GET/POST/DELETE /api/ai/documents — admin
- GET /api/ai/models, /providers, /settings, /prompts — admin
- POST /api/ai/providers/validate — admin
- PUT /api/ai/settings, /api/ai/prompts/{intent} — admin

Regular users can call:
- POST /api/ai/query
- POST /api/ai/follow-up

These tests don't exercise live LLM providers; we assert correct auth,
422 on missing fields, and that happy-path GETs return JSON.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_admin_only_endpoints_reject_non_admin(
    buyer_client: dict,
) -> None:
    client: httpx.AsyncClient = buyer_client["client"]
    for method, path in (
        ("GET", "/api/ai/documents"),
        ("POST", "/api/ai/documents"),
        ("GET", "/api/ai/models"),
        ("GET", "/api/ai/providers"),
        ("GET", "/api/ai/settings"),
        ("GET", "/api/ai/prompts"),
    ):
        r = await client.request(method, path, json={})
        assert r.status_code == 403, f"{method} {path}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_admin_only_endpoints_reject_anonymous(
    anonymous_client: httpx.AsyncClient,
) -> None:
    for method, path in (
        ("GET", "/api/ai/documents"),
        ("POST", "/api/ai/documents"),
        ("GET", "/api/ai/providers"),
        ("PUT", "/api/ai/settings"),
    ):
        r = await anonymous_client.request(method, path, json={})
        assert r.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_settings_roundtrip(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.get("/api/ai/settings")
    assert r.status_code == 200

    original = r.json() or {}

    r_update = await admin_client.put(
        "/api/ai/settings",
        json={"temperature": 0.42},
    )
    assert r_update.status_code == 200

    # Restore original temperature if present to be a good citizen.
    if "temperature" in original:
        await admin_client.put(
            "/api/ai/settings", json={"temperature": original["temperature"]}
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_settings_rejects_invalid_types(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.put(
        "/api/ai/settings",
        json={"temperature": "hot"},  # wrong type
    )
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_prompt_update_rejects_missing_template(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.put("/api/ai/prompts/rag_query", json={})
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_documents_list_and_upload_roundtrip(
    admin_client: httpx.AsyncClient,
) -> None:
    listed = await admin_client.get("/api/ai/documents")
    assert listed.status_code == 200

    upload = await admin_client.post(
        "/api/ai/documents",
        json={
            "filename": "e2e-doc.txt",
            "content": "Hello e2e.",
            "content_type": "text/plain",
        },
    )
    assert upload.status_code in (200, 201)
    body = upload.json()
    doc_id = body.get("id") or body.get("_id") or body.get("doc_id")
    if not doc_id:
        pytest.skip("upload did not return an id — skipping delete step")

    delete = await admin_client.delete(f"/api/ai/documents/{doc_id}")
    assert delete.status_code in (200, 204)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_query_requires_auth(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.post("/api/ai/query", json={"query": "hi"})
    assert r.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_query_validates_body(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    # Missing required `query` field.
    r = await client.post("/api/ai/query", json={})
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_follow_up_validates_body(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post("/api/ai/follow-up", json={})
    assert r.status_code == 422
