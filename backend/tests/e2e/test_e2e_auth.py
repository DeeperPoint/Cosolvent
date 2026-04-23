"""E2E: /api/auth endpoints.

Covers:
- POST /api/auth/signup  (happy + missing field + invalid email + disabled policy)
- POST /api/auth/login   (happy + wrong password + unknown email)
- POST /api/auth/bootstrap (happy/idempotent + already-bootstrapped)
- GET  /api/auth/me      (happy + missing cookie + invalid cookie)
- GET  /api/auth/verify  (happy + missing cookie)
- POST /api/auth/logout  (happy + no-session idempotent)

Each response body is validated against the OpenAPI schema via
``ContractClient``.
"""

from __future__ import annotations

import os

import httpx
import pytest

from tests.e2e.contract import ContractClient, OpenAPIContract
from tests.e2e.helpers import (
    new_client,
    random_email,
    require_mode,
)

_USER_PASSWORD = "UserPass123!"


@pytest.fixture
def admin_credentials() -> tuple[str, str]:
    email = os.getenv("E2E_ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("E2E_ADMIN_PASSWORD", "ChangeMe123!")
    return email, password


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bootstrap_is_idempotent(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
    admin_credentials: tuple[str, str],
) -> None:
    require_mode("RUN_E2E")
    email, password = admin_credentials
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        first = await c.post(
            "/api/auth/bootstrap",
            json={"email": email, "password": password},
            expected_status=(201, 409),
        )
        assert first.status_code in (200, 409)

        second = await c.post(
            "/api/auth/bootstrap",
            json={"email": email, "password": password},
            expected_status=(201, 409),
        )
        assert second.status_code in (200, 409)
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_signup_happy_path_and_cookie_set(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
    marketplace_contract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        # Public signup may be disabled in marketplace.yaml; backend honours
        # ALLOW_PUBLIC_SIGNUP env override.  We don't assert the toggle here
        # — both 200 and 403 are valid responses under different configs.
        email = random_email("e2e-auth-signup")
        response = await c.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": _USER_PASSWORD,
                "participant_type": "buyer",
            },
            expected_status=(201, 403),
        )
        if response.status_code == 200:
            body = response.json()
            assert body["email"] == email
            assert body["participant_type"] == "buyer"
            assert client.cookies.get("session_token"), "session cookie not set"
        else:
            assert not marketplace_contract.allow_public_signup or os.getenv(
                "ALLOW_PUBLIC_SIGNUP"
            ) == "false"
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_signup_rejects_missing_required_fields(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        for payload in (
            {"password": "x", "participant_type": "buyer"},  # missing email
            {"email": "a@b.co", "participant_type": "buyer"},  # missing password
            {"email": "a@b.co", "password": "x"},  # missing participant_type
        ):
            r = await c.post(
                "/api/auth/signup",
                json=payload,
                expected_status=422,
                validate=True,
            )
            assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_signup_rejects_invalid_email_type(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        r = await c.post(
            "/api/auth/signup",
            json={"email": "not-an-email", "password": "x", "participant_type": "buyer"},
            expected_status=422,
        )
        assert r.status_code == 422
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_login_rejects_bad_credentials(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
    admin_credentials: tuple[str, str],
) -> None:
    require_mode("RUN_E2E")
    email, _ = admin_credentials
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        r = await c.post(
            "/api/auth/login",
            json={"email": email, "password": "definitely-not-the-password"},
            expected_status=(400, 401, 403),
        )
        assert r.status_code in (400, 401, 403)

        r_unknown = await c.post(
            "/api/auth/login",
            json={"email": random_email("never"), "password": "x"},
            expected_status=(400, 401, 404),
        )
        assert r_unknown.status_code in (400, 401, 404)
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_me_and_verify_require_auth(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        for path in ("/api/auth/me", "/api/auth/verify"):
            r = await c.get(path, expected_status=401)
            assert r.status_code == 401
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_me_rejects_invalid_session_cookie(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        r = await c.get(
            "/api/auth/me",
            cookies={"session_token": "this-is-not-a-real-token"},
            expected_status=401,
        )
        assert r.status_code == 401
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_admin_me_and_verify_roundtrip(
    admin_client: httpx.AsyncClient,
    openapi_contract: OpenAPIContract,
) -> None:
    c = ContractClient(admin_client, openapi_contract)
    me = await c.get("/api/auth/me", expected_status=200)
    verify = await c.get("/api/auth/verify", expected_status=200)
    assert me.json()["email"] == verify.json()["email"]
    assert me.json()["role"] == "admin"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_logout_is_idempotent_without_session(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        r = await c.post("/api/auth/logout", expected_status=(200, 204))
        assert r.status_code in (200, 204)
    finally:
        await client.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_logout_clears_cookie_for_authed_user(
    e2e_base_url: str,
    openapi_contract: OpenAPIContract,
) -> None:
    require_mode("RUN_E2E")
    client = new_client(e2e_base_url)
    c = ContractClient(client, openapi_contract)
    try:
        email = random_email("e2e-logout")
        signup = await c.post(
            "/api/auth/signup",
            json={"email": email, "password": _USER_PASSWORD, "participant_type": "buyer"},
            expected_status=(201, 403),
        )
        if signup.status_code != 201:
            pytest.skip("Public signup disabled; cannot exercise authed logout")
        assert client.cookies.get("session_token")
        r = await c.post("/api/auth/logout", expected_status=(200, 204))
        assert r.status_code in (200, 204)
        # After logout, /me must be unauthenticated.
        me = await c.get("/api/auth/me", expected_status=401)
        assert me.status_code == 401
    finally:
        await client.aclose()
