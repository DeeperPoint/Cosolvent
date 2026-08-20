"""Tests for auth dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.dependencies import extract_bearer_token, get_current_user, get_optional_user


@pytest.mark.asyncio
async def test_get_current_user_blocks_deactivated_account():
    now = datetime.now(timezone.utc)
    sessions = AsyncMock()
    sessions.find_one = AsyncMock(
        return_value={"token": "t", "user_id": "u1", "expires_at": now + timedelta(hours=1)}
    )
    users = AsyncMock()
    users.find_one = AsyncMock(return_value={"_id": "u1", "email": "x@example.com", "is_active": False})

    def fake_get_collection(name: str):
        if name == "sessions":
            return sessions
        if name == "users":
            return users
        raise AssertionError("unexpected collection")

    with patch("app.core.dependencies.get_collection", side_effect=fake_get_collection):
        with pytest.raises(HTTPException) as exc:
            await get_current_user("t")
    assert exc.value.status_code == 403
    assert "deactivated" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_accepts_naive_future_expiry():
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    sessions = AsyncMock()
    sessions.find_one = AsyncMock(
        return_value={"token": "t", "user_id": "u1", "expires_at": now_naive + timedelta(hours=1)}
    )
    users = AsyncMock()
    users.find_one = AsyncMock(return_value={"_id": "u1", "email": "x@example.com", "is_active": True})

    def fake_get_collection(name: str):
        if name == "sessions":
            return sessions
        if name == "users":
            return users
        raise AssertionError("unexpected collection")

    with patch("app.core.dependencies.get_collection", side_effect=fake_get_collection):
        user = await get_current_user("t")
    assert user["_id"] == "u1"


@pytest.mark.asyncio
async def test_get_current_user_rejects_naive_expired_session():
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    sessions = AsyncMock()
    sessions.find_one = AsyncMock(
        return_value={"token": "t", "user_id": "u1", "expires_at": now_naive - timedelta(seconds=1)}
    )
    users = AsyncMock()
    users.find_one = AsyncMock(return_value={"_id": "u1", "email": "x@example.com", "is_active": True})

    def fake_get_collection(name: str):
        if name == "sessions":
            return sessions
        if name == "users":
            return users
        raise AssertionError("unexpected collection")

    with patch("app.core.dependencies.get_collection", side_effect=fake_get_collection):
        with pytest.raises(HTTPException) as exc:
            await get_current_user("t")
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_rejects_malformed_expiry_and_cleans_session():
    sessions = AsyncMock()
    sessions.find_one = AsyncMock(
        return_value={"_id": "s1", "token": "t", "user_id": "u1", "expires_at": "not-a-date"}
    )
    sessions.delete_one = AsyncMock(return_value=None)
    users = AsyncMock()
    users.find_one = AsyncMock(return_value={"_id": "u1", "email": "x@example.com", "is_active": True})

    def fake_get_collection(name: str):
        if name == "sessions":
            return sessions
        if name == "users":
            return users
        raise AssertionError("unexpected collection")

    with patch("app.core.dependencies.get_collection", side_effect=fake_get_collection):
        with pytest.raises(HTTPException) as exc:
            await get_current_user("t")
    assert exc.value.status_code == 401
    sessions.delete_one.assert_awaited_once_with({"_id": "s1"})


# ── GAP-1: Authorization: Bearer as a cross-origin alternative to the cookie ──────────

@pytest.mark.parametrize(
    "header,expected",
    [
        (None, None),
        ("", None),
        ("Bearer", None),  # scheme with no token
        ("Bearer ", None),
        ("Basic dXNlcjpwYXNz", None),  # different scheme — not our concern
        ("Bearer abc123", "abc123"),
        ("bearer abc123", "abc123"),  # scheme is case-insensitive
    ],
)
def test_extract_bearer_token(header, expected):
    assert extract_bearer_token(header) == expected


def _fake_get_collection_for(user_id: str, token: str):
    now = datetime.now(timezone.utc)
    sessions = AsyncMock()
    sessions.find_one = AsyncMock(
        return_value={"token": token, "user_id": user_id, "expires_at": now + timedelta(hours=1)}
    )
    users = AsyncMock()
    users.find_one = AsyncMock(return_value={"_id": user_id, "email": "x@example.com", "is_active": True})

    def fake_get_collection(name: str):
        if name == "sessions":
            return sessions
        if name == "users":
            return users
        raise AssertionError("unexpected collection")

    return fake_get_collection


@pytest.mark.asyncio
async def test_get_current_user_resolves_from_bearer_header_with_no_cookie():
    with patch(
        "app.core.dependencies.get_collection",
        side_effect=_fake_get_collection_for("u1", "header-token"),
    ):
        user = await get_current_user(session_token=None, authorization="Bearer header-token")
    assert user["_id"] == "u1"


@pytest.mark.asyncio
async def test_get_current_user_prefers_bearer_header_over_cookie():
    """A caller that sets Authorization is asserting bearer auth; it should win even if a
    (possibly stale) cookie is also present."""
    with patch(
        "app.core.dependencies.get_collection",
        side_effect=_fake_get_collection_for("u2", "header-token"),
    ):
        user = await get_current_user(session_token="cookie-token", authorization="Bearer header-token")
    assert user["_id"] == "u2"


@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_cookie_when_no_bearer_header():
    with patch(
        "app.core.dependencies.get_collection",
        side_effect=_fake_get_collection_for("u3", "cookie-token"),
    ):
        user = await get_current_user(session_token="cookie-token", authorization=None)
    assert user["_id"] == "u3"


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_with_no_cookie_or_header():
    assert await get_optional_user(session_token=None, authorization=None) is None


@pytest.mark.asyncio
async def test_get_optional_user_resolves_from_bearer_header():
    with patch(
        "app.core.dependencies.get_collection",
        side_effect=_fake_get_collection_for("u4", "header-token"),
    ):
        user = await get_optional_user(session_token=None, authorization="Bearer header-token")
    assert user["_id"] == "u4"
