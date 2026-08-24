"""CSRF posture and API-key authentication over HTTP (GAP-1).

The CSRF cases need no database: the middleware runs ahead of routing, so an
unrouted path distinguishes "blocked" (403) from "allowed through" (404) without
touching authentication. Only the API-key lifecycle is gated by RUN_INTEGRATION.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import close_db, connect_db, get_collection
from app.main import create_app
from app.modules.auth import api_keys
from tests.e2e.helpers import require_mode

ALLOWED_ORIGIN = "http://localhost:3000"
FOREIGN_ORIGIN = "https://attacker.example"
# Unrouted on purpose — see module docstring.
CSRF_PROBE = "/api/__csrf_probe__"


@pytest.fixture
def app():
    return create_app()


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ── CSRF, once SameSite is relaxed ───────────────────────────────────────

@pytest.mark.asyncio
async def test_cookie_write_without_origin_is_rejected(app, monkeypatch):
    """SameSite=none removes the browser's own CSRF protection; a cookie write
    carrying no Origin must be refused."""
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "whatever")
        res = await client.post(CSRF_PROBE, json={})
    assert res.status_code == 403
    assert "cross-site" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cookie_write_from_foreign_origin_is_rejected(app, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "whatever")
        res = await client.post(CSRF_PROBE, json={}, headers={"Origin": FOREIGN_ORIGIN})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cookie_write_from_allowlisted_origin_passes(app, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "invalid-but-present")
        res = await client.post(CSRF_PROBE, json={}, headers={"Origin": ALLOWED_ORIGIN})
    assert res.status_code == 404  # reached routing, so CSRF let it through


@pytest.mark.asyncio
async def test_bearer_write_is_exempt(app, monkeypatch):
    """A bearer token is attached deliberately, never ambiently by the browser."""
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "whatever")
        res = await client.post(
            CSRF_PROBE, json={}, headers={"Authorization": "Bearer tok"}
        )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_key_write_is_exempt(app, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "whatever")
        res = await client.post(CSRF_PROBE, json={}, headers={"X-API-Key": "csk_x"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_no_check_when_same_site(app, monkeypatch):
    """With SameSite=lax the browser already withholds the cookie cross-site, so
    the extra check must not fire and break same-origin clients."""
    monkeypatch.setattr(settings, "session_cookie_samesite", "lax")
    async with _client(app) as client:
        client.cookies.set("session_token", "invalid-but-present")
        res = await client.post(CSRF_PROBE, json={})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reads_are_never_blocked(app, monkeypatch):
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        client.cookies.set("session_token", "whatever")
        res = await client.get("/api/health")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_anonymous_write_is_not_blocked(app, monkeypatch):
    """No cookie means no ambient credential to ride — signup and login must
    still work from any origin."""
    monkeypatch.setattr(settings, "session_cookie_samesite", "none")
    async with _client(app) as client:
        res = await client.post(CSRF_PROBE, json={})
    assert res.status_code == 404


# ── API-key lifecycle ────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_lifecycle_and_authentication(app):
    require_mode("RUN_INTEGRATION")

    await connect_db()
    try:
        users = get_collection("users")
        result = await users.insert_one(
            {"email": "apikey-test@example.com", "role": "user", "is_active": True}
        )
        user_id = str(result.inserted_id)

        try:
            plaintext, record = await api_keys.create_api_key(user_id, "sponsor backend")

            # Returned once; stored only as a hash.
            assert plaintext.startswith(api_keys.API_KEY_PREFIX)
            assert record["key_hash"] != plaintext
            assert plaintext not in str(record)

            # It authenticates.
            resolved = await api_keys.resolve_api_key(plaintext)
            assert resolved is not None and str(resolved["_id"]) == user_id

            # Wrong or malformed keys do not.
            assert await api_keys.resolve_api_key(api_keys.generate_api_key()) is None
            assert await api_keys.resolve_api_key("not-a-key") is None

            # Listing never exposes secret material.
            listed = await api_keys.list_api_keys(user_id)
            assert len(listed) == 1
            assert plaintext not in str(listed)
            assert listed[0]["key_hint"] == plaintext[-4:]

            # It authenticates over HTTP too.
            async with _client(app) as client:
                res = await client.get("/api/auth/me", headers={"X-API-Key": plaintext})
                assert res.status_code == 200, res.text

            # Revocation is immediate.
            assert await api_keys.revoke_api_key(user_id, str(record["_id"])) is True
            assert await api_keys.resolve_api_key(plaintext) is None

            async with _client(app) as client:
                res = await client.get("/api/auth/me", headers={"X-API-Key": plaintext})
                assert res.status_code == 401

            # One user cannot revoke another's key.
            assert await api_keys.revoke_api_key("someone-else", str(record["_id"])) is False
        finally:
            await get_collection("api_keys").delete_one({"user_id": user_id})
            await users.delete_one({"_id": result.inserted_id})
    finally:
        await close_db()


# ── access_token is opt-in ───────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_access_token_is_returned_only_on_request(app):
    """The HttpOnly cookie exists so page scripts cannot read the session token.
    Returning that same value in the body by default hands it to JavaScript
    anyway, so it is opt-in for callers that genuinely cannot use cookies."""
    require_mode("RUN_INTEGRATION")

    from app.modules.auth import repository as auth_repo
    from app.core.security import hash_password

    await connect_db()
    try:
        email = "optin-test@example.com"
        password = "correct-horse-battery"

        await get_collection("users").delete_one({"email": email})
        await auth_repo.create_user(email, hash_password(password), "producer")

        try:
            async with _client(app) as client:
                default = await client.post(
                    "/api/auth/login", json={"email": email, "password": password}
                )
                assert default.status_code == 200, default.text
                # Present-but-null is fine; what matters is that no usable token
                # is handed to page scripts by default.
                assert default.json().get("access_token") is None
                # The browser path is unchanged - the cookie is still set.
                assert "session_token" in default.cookies

            async with _client(app) as client:
                opted_in = await client.post(
                    "/api/auth/login",
                    json={"email": email, "password": password},
                    headers={"X-Auth-Mode": "bearer"},
                )
                assert opted_in.status_code == 200, opted_in.text
                token = opted_in.json().get("access_token")
                assert token

                # And it genuinely authenticates.
                me = await client.get(
                    "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
                )
                assert me.status_code == 200
        finally:
            await get_collection("users").delete_one({"email": email})
    finally:
        await close_db()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_is_throttled_and_audited(app):
    """Login carries its own throttle because CORS does nothing about scripted
    credential stuffing, and both the failures and the throttle are recorded."""
    require_mode("RUN_INTEGRATION")

    from app.core import rate_limit

    rate_limit.reset()
    await connect_db()
    try:
        email = "throttle-test@example.com"
        async with _client(app) as client:
            statuses = [
                (
                    await client.post(
                        "/api/auth/login", json={"email": email, "password": "wrong"}
                    )
                ).status_code
                for _ in range(rate_limit.LOGIN_ACCOUNT_LIMIT + 2)
            ]

        assert 429 in statuses, f"expected a throttle, got {statuses}"

        events = (
            await get_collection("auth_audit").find({"email": email}).to_list(length=None)
        )
        names = {e["event"] for e in events}
        assert audit_events_recorded(names)

        for event in events:
            await get_collection("auth_audit").delete_one({"_id": event["_id"]})
    finally:
        rate_limit.reset()
        await close_db()


def audit_events_recorded(names: set[str]) -> bool:
    from app.modules.auth import audit

    return audit.LOGIN_FAILED in names and audit.LOGIN_THROTTLED in names
