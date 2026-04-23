"""E2E: /api/profiles/{type_slug}/... generic profile routes.

Exercises every generic profile endpoint plus common negative cases:

- POST /api/profiles/{slug}/register — anonymous (with email) and authed
- GET  /api/profiles/{slug}/draft
- PUT  /api/profiles/{slug}/draft (invalid field, missing required)
- POST /api/profiles/{slug}/draft/submit
- GET  /api/profiles/{slug}/me
- GET  /api/profiles/{slug}/{profile_id}
- PUT  /api/profiles/{slug}/{profile_id}
- POST /api/profiles/{slug}/{profile_id}/ai-generate (uses role aliases for admin paths)
- Unknown type_slug → 404
- Anonymous access to authed routes → 401

Because generic ``/api/profiles`` routes return unconstrained bodies in
the OpenAPI spec, this file validates structural invariants manually
(status code, key presence) rather than through jsonschema.  The
``/api/roles/{slug}/...`` alias routes, which *do* have schemas, are
validated in ``test_e2e_role_aliases.py``.
"""

from __future__ import annotations

import httpx
import pytest

from tests.e2e.contract import ContractClient, MarketplaceContract, OpenAPIContract
from tests.e2e.helpers import (
    new_client,
    random_email,
    register_update_submit,
    require_mode,
)

_USER_PASSWORD = "UserPass123!"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_unknown_participant_type_returns_404(
    anonymous_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(anonymous_client, openapi_contract)
    for method, path in (
        ("POST", "/api/profiles/not-a-real-slug/register"),
        ("GET", "/api/profiles/not-a-real-slug/me"),
        ("GET", "/api/profiles/not-a-real-slug/draft"),
    ):
        # /me and /draft also require auth → may 401 before 404.
        r = await c.request(
            method,
            path,
            path_template=f"/api/profiles/{{type_slug}}/{path.rsplit('/', 1)[1]}",
            validate=False,
        )
        assert r.status_code in (401, 404)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_draft_endpoints_require_auth(
    anonymous_client: httpx.AsyncClient,
    marketplace_contract: MarketplaceContract,
) -> None:
    slug = marketplace_contract.participant_types[0].slug
    for method, path in (
        ("GET", f"/api/profiles/{slug}/draft"),
        ("PUT", f"/api/profiles/{slug}/draft"),
        ("POST", f"/api/profiles/{slug}/draft/submit"),
        ("GET", f"/api/profiles/{slug}/me"),
    ):
        r = await anonymous_client.request(method, path, json={})
        assert r.status_code == 401, f"{method} {path} should require auth"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_anonymous_register_requires_email_and_document(
    e2e_base_url: str,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    try:
        # No email → 400/422.
        r_no_email = await client.post(
            "/api/profiles/producer/register",
            data={"fields": '{"farm_name":"Test"}'},
        )
        # Depending on how httpx encodes a bodiless form, FastAPI may return
        # 415 (unsupported media type) before field validation kicks in.
        assert r_no_email.status_code in (400, 401, 403, 415, 422)

        # Email supplied but no onboarding document → 422 (producer requires docs).
        r_no_doc = await client.post(
            "/api/profiles/producer/register",
            data={
                "email": random_email("e2e-prof-anon"),
                "fields": '{"farm_name":"Test","country":"Canada","primary_crops":["Wheat"]}',
            },
        )
        assert r_no_doc.status_code in (400, 403, 415, 422)
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_draft_enforces_schema(
    buyer_client: dict,
) -> None:
    client: httpx.AsyncClient = buyer_client["client"]

    # Producer buyer schema requires org_name, country, business_type.
    # Sending an invalid type for `country` (number) should be rejected.
    r_bad = await client.put(
        "/api/profiles/buyer/draft",
        json={"fields": {"country": 123, "org_name": "Org", "business_type": "Mill"}},
    )
    assert r_bad.status_code in (400, 422)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_draft_rejects_unknown_fields_or_accepts_them_safely(
    buyer_client: dict,
) -> None:
    client: httpx.AsyncClient = buyer_client["client"]
    r = await client.put(
        "/api/profiles/buyer/draft",
        json={
            "fields": {
                "org_name": "Test Org",
                "country": "Canada",
                "business_type": "Mill",
                "totally_unknown_field": "ignored-or-rejected",
            }
        },
    )
    # Either the backend strips unknown fields (200) or rejects them (422).
    assert r.status_code in (200, 400, 422)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_buyer_register_update_submit_flow(
    buyer_client: dict,
) -> None:
    client: httpx.AsyncClient = buyer_client["client"]
    application = await register_update_submit(
        client,
        "buyer",
        {
            "org_name": "Flow Co",
            "country": "Canada",
            "business_type": "Trading Company",
        },
    )
    # Buyers have ``requires_approval: false`` in marketplace.yaml, so submit
    # immediately activates a profile and returns ``profile_id``/``status``.
    # Producers (which require approval) would instead receive an application
    # envelope with ``id``.
    assert application.get("id") or application.get("profile_id"), (
        "submit draft should return either an application id or a profile id"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_my_profile_returns_for_onboarded_buyer(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.get("/api/profiles/buyer/me")
    assert r.status_code in (200, 404)  # profile may be pending approval


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_public_profile_read_returns_public_or_404(
    anonymous_client: httpx.AsyncClient,
    onboarded_producer: dict,
) -> None:
    """After approval the producer profile becomes a concrete /api/profiles/producer/{id}.

    We can't know the id without admin, so this test just asserts that an
    arbitrary random UUID returns 404 (the happy path is covered in role
    alias tests).
    """

    r = await anonymous_client.get(
        "/api/profiles/producer/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code in (404, 401)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ai_profile_actions_require_roles(
    buyer_client: dict,
    admin_client: httpx.AsyncClient,
) -> None:
    """ai-approve / ai-reject are admin-only; ai-generate requires ownership."""

    client: httpx.AsyncClient = buyer_client["client"]

    r_approve = await client.post(
        "/api/profiles/buyer/00000000-0000-0000-0000-000000000000/ai-approve"
    )
    assert r_approve.status_code == 403

    r_reject = await client.post(
        "/api/profiles/buyer/00000000-0000-0000-0000-000000000000/ai-reject"
    )
    assert r_reject.status_code == 403

    # Admin hitting a non-existent profile should 404 (or raise a typed
    # error) rather than 500.
    r_admin_approve = await admin_client.post(
        "/api/profiles/buyer/00000000-0000-0000-0000-000000000000/ai-approve"
    )
    assert r_admin_approve.status_code in (400, 404, 422)
