"""API-key principals and the credentialed-CORS guard (GAP-1).

Complements `test_settings.py` (SameSite validation) and `test_dependencies.py`
(bearer parsing), which cover the cookie and bearer channels. This file covers
the third channel — API keys — and the wildcard-origin guard.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import dependencies
from app.core.config import Settings
from app.modules.auth import api_keys


class TestCredentialedCorsGuard:
    def test_wildcard_origin_is_rejected(self):
        """`Allow-Origin: *` is invalid alongside credentials — it would disable the
        cross-origin login it appears to enable."""
        with pytest.raises(ValidationError, match="cannot contain"):
            Settings(cors_origins=["*"])

    def test_wildcard_among_valid_origins_is_still_rejected(self):
        with pytest.raises(ValidationError, match="cannot contain"):
            Settings(cors_origins=["https://sponsor.example", "*"])

    def test_explicit_origins_are_accepted(self):
        s = Settings(cors_origins=["https://sponsor.example", "http://localhost:3000"])
        assert "https://sponsor.example" in s.cors_origins


class TestApiKeyPrimitives:
    def test_generated_key_is_prefixed_and_unique(self):
        a, b = api_keys.generate_api_key(), api_keys.generate_api_key()
        assert a.startswith(api_keys.API_KEY_PREFIX)
        assert a != b

    def test_hash_is_stable_and_hides_the_plaintext(self):
        key = api_keys.generate_api_key()
        assert api_keys.hash_api_key(key) == api_keys.hash_api_key(key)
        assert key not in api_keys.hash_api_key(key)

    def test_distinct_keys_hash_differently(self):
        assert api_keys.hash_api_key("csk_a") != api_keys.hash_api_key("csk_b")

    @pytest.mark.parametrize(
        "value,expected",
        [("csk_abc", True), ("sk_abc", False), ("", False), (None, False)],
    )
    def test_shape_check(self, value, expected):
        assert api_keys.looks_like_api_key(value) is expected


class TestApiKeyChannel:
    async def test_api_key_takes_precedence_over_cookie(self, monkeypatch):
        """An explicit credential must not be overridden by whoever happens to be
        signed in in the same browser."""
        async def fake_resolve(key):
            return {"_id": "api-user", "email": "svc@example.com"}

        monkeypatch.setattr(api_keys, "resolve_api_key", fake_resolve)
        user = await dependencies.get_current_user(
            session_token="cookie-token", authorization=None, x_api_key="csk_valid"
        )
        assert user["_id"] == "api-user"

    async def test_invalid_api_key_raises_rather_than_falling_back(self, monkeypatch):
        """A bad key must fail closed, never silently downgrade to the cookie."""
        async def fake_resolve(key):
            return None

        monkeypatch.setattr(api_keys, "resolve_api_key", fake_resolve)
        with pytest.raises(HTTPException) as exc:
            await dependencies.get_current_user(
                session_token="cookie-token", authorization=None, x_api_key="csk_bad"
            )
        assert exc.value.status_code == 401

    async def test_optional_user_returns_none_for_invalid_key(self, monkeypatch):
        async def fake_resolve(key):
            return None

        monkeypatch.setattr(api_keys, "resolve_api_key", fake_resolve)
        assert (
            await dependencies.get_optional_user(
                session_token=None, authorization=None, x_api_key="csk_bad"
            )
            is None
        )

    async def test_absent_api_key_leaves_existing_channels_untouched(self, monkeypatch):
        """The header must not disturb the cookie/bearer path when unset."""
        seen = {}

        async def fake_from_token(token):
            seen["token"] = token
            return {"_id": "u1"}

        monkeypatch.setattr(dependencies, "get_current_user_from_token", fake_from_token)
        await dependencies.get_current_user(
            session_token="cookie-token", authorization=None, x_api_key=None
        )
        assert seen["token"] == "cookie-token"
