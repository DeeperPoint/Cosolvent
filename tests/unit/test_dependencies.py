"""Tests for auth dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_user


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
