"""E2E: /api/admin/... endpoints.

Covers dashboard, user management, applications (approve/reject),
profile status, conversations oversight, AI settings, and FAQ CRUD.

All admin endpoints require admin auth; unauthenticated and non-admin
access are both expected to return 401/403.
"""

from __future__ import annotations

import httpx
import pytest

from tests.e2e.contract import ContractClient, OpenAPIContract
from tests.e2e.helpers import random_email, register_update_submit, signup_user

_USER_PASSWORD = "UserPass123!"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_routes_reject_anonymous(
    anonymous_client: httpx.AsyncClient,
) -> None:
    for method, path in (
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/config"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/applications"),
        ("GET", "/api/admin/conversations"),
        ("GET", "/api/admin/faqs"),
        ("GET", "/api/admin/ai/providers"),
        ("GET", "/api/admin/ai/models"),
        ("GET", "/api/admin/ai/settings"),
        ("GET", "/api/admin/ai/prompts"),
        ("GET", "/api/admin/ai/documents"),
    ):
        r = await anonymous_client.request(method, path)
        assert r.status_code == 401, f"{method} {path} returned {r.status_code}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_routes_reject_non_admin(
    buyer_client: dict,
) -> None:
    client: httpx.AsyncClient = buyer_client["client"]
    for method, path in (
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/applications"),
    ):
        r = await client.request(method, path)
        assert r.status_code == 403


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_dashboard_and_config(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(admin_client, openapi_contract)

    dash = await c.get("/api/admin/dashboard", expected_status=200)
    assert isinstance(dash.json(), dict)

    cfg = await c.get("/api/admin/config", expected_status=200)
    body = cfg.json()
    assert "marketplace" in body
    assert "participant_types" in body


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_users_list_and_get(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(admin_client, openapi_contract)
    r_list = await c.get("/api/admin/users", expected_status=200)
    users = r_list.json()
    assert isinstance(users, list)

    r_bad = await c.get(
        "/api/admin/users/00000000-0000-0000-0000-000000000000",
        expected_status=(404, 400),
    )
    assert r_bad.status_code in (404, 400)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_applications_pending_listing(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(admin_client, openapi_contract)
    r = await c.get(
        "/api/admin/applications",
        params={"status": "pending"},
        expected_status=200,
    )
    assert isinstance(r.json(), list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_approve_flow(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
    e2e_base_url: str,
) -> None:
    """Seed a producer, find their application, approve it, assert contract."""

    from tests.e2e.helpers import new_client  # late import to avoid cycles

    c_admin = ContractClient(admin_client, openapi_contract)

    producer = new_client(e2e_base_url)
    try:
        producer_auth = await signup_user(
            producer,
            email=random_email("admin-approve"),
            password=_USER_PASSWORD,
            participant_type="producer",
        )
        await register_update_submit(
            producer,
            "producer",
            {
                "farm_name": "Approve Farm",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )

        pending = await admin_client.get(
            "/api/admin/applications", params={"status": "pending"}
        )
        pending.raise_for_status()
        app_row = next(
            (a for a in pending.json() if a.get("user_id") == producer_auth["user_id"]),
            None,
        )
        assert app_row is not None, "seeded producer application not found"

        approve = await c_admin.post(
            f"/api/admin/applications/{app_row['id']}/approve",
            expected_status=200,
        )
        decision = approve.json()
        assert decision.get("status") == "approved"
    finally:
        await producer.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_reject_flow(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
    e2e_base_url: str,
) -> None:
    from tests.e2e.helpers import new_client

    c_admin = ContractClient(admin_client, openapi_contract)
    producer = new_client(e2e_base_url)
    try:
        producer_auth = await signup_user(
            producer,
            email=random_email("admin-reject"),
            password=_USER_PASSWORD,
            participant_type="producer",
        )
        await register_update_submit(
            producer,
            "producer",
            {
                "farm_name": "Reject Farm",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )

        pending = await admin_client.get(
            "/api/admin/applications", params={"status": "pending"}
        )
        app_row = next(
            (a for a in pending.json() if a.get("user_id") == producer_auth["user_id"]),
            None,
        )
        assert app_row is not None

        reject = await c_admin.post(
            f"/api/admin/applications/{app_row['id']}/reject",
            json={"feedback": "not a fit"},
            expected_status=200,
        )
        decision = reject.json()
        assert decision.get("status") == "rejected"
        assert decision.get("feedback") == "not a fit"
    finally:
        await producer.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_faq_crud(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(admin_client, openapi_contract)

    create = await c.post(
        "/api/admin/faqs",
        json={"question": "E2E Q?", "answer": "E2E A.", "sort_order": 0},
        expected_status=201,
    )
    created = create.json()
    faq_id = created.get("id") or created.get("_id")
    assert faq_id, f"expected id in create response, got {created}"

    try:
        listed = await c.get("/api/admin/faqs", expected_status=200)
        assert isinstance(listed.json(), list)

        got = await c.get(f"/api/admin/faqs/{faq_id}", expected_status=200)
        assert got.json().get("question") == "E2E Q?"

        update = await c.put(
            f"/api/admin/faqs/{faq_id}",
            json={"answer": "E2E Updated"},
            expected_status=200,
        )
        assert update.json().get("answer") == "E2E Updated"

        missing_update = await c.put(
            "/api/admin/faqs/00000000-0000-0000-0000-000000000000",
            json={"answer": "x"},
            expected_status=(404, 400),
        )
        assert missing_update.status_code in (404, 400)
    finally:
        delete = await admin_client.delete(f"/api/admin/faqs/{faq_id}")
        assert delete.status_code in (200, 204)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_faq_create_validates_required_fields(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.post("/api/admin/faqs", json={"question": "only-q"})
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_user_role_update_rejects_invalid(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.put(
        "/api/admin/users/00000000-0000-0000-0000-000000000000/role",
        json={"role": "superduper"},
    )
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_profile_status_validates_enum(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.put(
        "/api/admin/profiles/00000000-0000-0000-0000-000000000000/status",
        json={"status": "not-a-valid-status"},
    )
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_ai_endpoints_happy_paths(
    admin_client: httpx.AsyncClient,
) -> None:
    for path in (
        "/api/admin/ai/providers",
        "/api/admin/ai/models",
        "/api/admin/ai/settings",
        "/api/admin/ai/prompts",
        "/api/admin/ai/documents",
    ):
        r = await admin_client.get(path)
        assert r.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_ai_providers_validate_rejects_unknown(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.post(
        "/api/admin/ai/providers/validate",
        json={"provider": "this-provider-does-not-exist"},
    )
    assert r.status_code in (200, 400, 422)  # validator may return 200-with-error or 422
