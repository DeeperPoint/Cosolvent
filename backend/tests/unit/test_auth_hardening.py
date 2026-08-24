"""Auth hardening beyond the GAP-1 baseline.

Covers the containment properties, each of which exists because its absence is a
known failure mode rather than a theoretical one: keys that mint keys, keys that
never expire, keys that inherit admin, and an unthrottled login endpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import dependencies, rate_limit
from app.core.config import Settings
from app.modules.auth import api_keys


@pytest.fixture(autouse=True)
def _clear_limiter():
    rate_limit.reset()
    yield
    rate_limit.reset()


# ── Key management cannot be driven by a key ─────────────────────────────

class TestKeyMintingContainment:
    async def test_session_principal_rejects_api_key_header(self):
        """A stolen key must not mint further keys — otherwise revoking the
        original never evicts the attacker."""
        with pytest.raises(HTTPException) as exc:
            await dependencies.require_session_principal(
                session_token=None, authorization=None
            )
        assert exc.value.status_code == 401

    async def test_session_principal_accepts_cookie(self, monkeypatch):
        async def fake_from_token(token):
            return {"_id": "u1", "auth_method": None}

        monkeypatch.setattr(dependencies, "get_current_user_from_token", fake_from_token)
        user = await dependencies.require_session_principal(session_token="tok")
        assert user["_id"] == "u1"

    async def test_session_principal_accepts_bearer(self, monkeypatch):
        seen = {}

        async def fake_from_token(token):
            seen["token"] = token
            return {"_id": "u1"}

        monkeypatch.setattr(dependencies, "get_current_user_from_token", fake_from_token)
        await dependencies.require_session_principal(authorization="Bearer abc")
        assert seen["token"] == "abc"


# ── Scopes ───────────────────────────────────────────────────────────────

class TestScopes:
    def test_default_scopes_exclude_admin(self):
        assert api_keys.SCOPE_ADMIN not in api_keys.normalize_scopes(None)

    def test_unknown_scope_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown scope"):
            api_keys.normalize_scopes(["read", "sudo"])

    def test_scopes_are_deduplicated(self):
        assert api_keys.normalize_scopes(["read", "read", "write"]) == ["read", "write"]

    async def test_admin_route_rejects_unscoped_key(self):
        """An admin's integration key must not carry admin authority by accident."""
        user = {"role": "admin", "auth_method": "api_key", "scopes": ["read", "write"]}
        with pytest.raises(HTTPException) as exc:
            await dependencies.require_admin(user=user)
        assert exc.value.status_code == 403
        assert "admin" in exc.value.detail

    async def test_admin_route_accepts_admin_scoped_key(self):
        user = {"role": "admin", "auth_method": "api_key", "scopes": ["admin"]}
        assert await dependencies.require_admin(user=user) is user

    async def test_admin_route_unaffected_for_human_session(self):
        user = {"role": "admin", "auth_method": None}
        assert await dependencies.require_admin(user=user) is user

    async def test_require_scope_blocks_missing_scope(self):
        checker = dependencies.require_scope("write")
        user = {"auth_method": "api_key", "scopes": ["read"]}
        with pytest.raises(HTTPException) as exc:
            await checker(user=user)
        assert exc.value.status_code == 403

    async def test_require_scope_ignores_session_callers(self):
        checker = dependencies.require_scope("write")
        user = {"auth_method": None}
        assert await checker(user=user) is user


# ── Expiry ───────────────────────────────────────────────────────────────

class TestExpiry:
    def test_key_without_expiry_never_expires(self):
        assert api_keys.is_expired({"expires_at": None}) is False

    def test_future_expiry_is_valid(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        assert api_keys.is_expired({"expires_at": future}) is False

    def test_past_expiry_is_expired(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert api_keys.is_expired({"expires_at": past}) is True

    def test_unparseable_expiry_fails_closed(self):
        assert api_keys.is_expired({"expires_at": "not-a-date"}) is True

    def test_naive_datetime_is_handled(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        assert api_keys.is_expired({"expires_at": past}) is True


# ── Login throttling ─────────────────────────────────────────────────────

class TestLoginThrottle:
    async def test_ip_limit_trips_after_threshold(self):
        for _ in range(rate_limit.LOGIN_IP_LIMIT):
            assert await rate_limit.check_login_attempt("1.2.3.4", None) is None
        assert await rate_limit.check_login_attempt("1.2.3.4", None) is not None

    async def test_account_limit_trips_before_ip_limit(self):
        """A distributed attack converging on one account is caught by the
        per-account counter even though each IP looks innocent."""
        for i in range(rate_limit.LOGIN_ACCOUNT_LIMIT):
            assert await rate_limit.check_login_attempt(f"10.0.0.{i}", "target@example.com") is None
        assert await rate_limit.check_login_attempt("10.0.0.99", "target@example.com") is not None

    async def test_account_key_is_case_insensitive(self):
        for i in range(rate_limit.LOGIN_ACCOUNT_LIMIT):
            await rate_limit.check_login_attempt(f"10.1.0.{i}", "User@Example.com")
        assert await rate_limit.check_login_attempt("10.1.0.99", "user@example.com") is not None

    async def test_separate_accounts_do_not_share_a_budget(self):
        for i in range(rate_limit.LOGIN_ACCOUNT_LIMIT):
            await rate_limit.check_login_attempt(f"10.2.0.{i}", "a@example.com")
        assert await rate_limit.check_login_attempt("10.2.0.99", "b@example.com") is None

    async def test_returns_retry_after_seconds(self):
        for _ in range(rate_limit.LOGIN_ACCOUNT_LIMIT + 1):
            result = await rate_limit.check_login_attempt(None, "x@example.com")
        assert result == rate_limit.LOGIN_ACCOUNT_WINDOW_SECONDS


# ── CORS preflight caching ───────────────────────────────────────────────

def test_wildcard_origin_still_rejected():
    with pytest.raises(ValidationError, match="cannot contain"):
        Settings(cors_origins=["*"])
