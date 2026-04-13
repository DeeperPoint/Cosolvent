"""Tests for notifications service layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.modules.notifications import service


@pytest.fixture
def mock_repo():
    with patch("app.modules.notifications.service.repo") as mock:
        yield mock


def _fake_notification(
    notif_id="notif-1",
    user_id="u1",
    notif_type="profile_approved",
    is_read=False,
):
    return {
        "_id": notif_id,
        "user_id": user_id,
        "type": notif_type,
        "data": {"message": "Your profile was approved"},
        "is_read": is_read,
        "created_at": "2026-01-15T12:00:00+00:00",
    }


class TestCreateNotification:
    @pytest.mark.asyncio
    async def test_creates_and_returns_formatted_response(self, mock_repo):
        mock_repo.create_notification = AsyncMock(return_value=_fake_notification())
        result = await service.create_notification("u1", "profile_approved", {"message": "Approved"})
        assert result["id"] == "notif-1"
        assert result["user_id"] == "u1"
        assert result["type"] == "profile_approved"
        assert result["is_read"] is False

    @pytest.mark.asyncio
    async def test_passes_correct_args_to_repo(self, mock_repo):
        mock_repo.create_notification = AsyncMock(return_value=_fake_notification())
        await service.create_notification("u1", "message_received", {"sender": "u2"})
        mock_repo.create_notification.assert_awaited_once_with("u1", "message_received", {"sender": "u2"})


class TestListNotifications:
    @pytest.mark.asyncio
    async def test_returns_formatted_list(self, mock_repo):
        mock_repo.list_notifications = AsyncMock(
            return_value=[
                _fake_notification("n1"),
                _fake_notification("n2", is_read=True),
            ]
        )
        result = await service.list_notifications("u1")
        assert len(result) == 2
        assert result[0]["id"] == "n1"
        assert result[0]["is_read"] is False
        assert result[1]["id"] == "n2"
        assert result[1]["is_read"] is True

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_repo):
        mock_repo.list_notifications = AsyncMock(return_value=[])
        result = await service.list_notifications("u1")
        assert result == []

    @pytest.mark.asyncio
    async def test_passes_skip_and_limit(self, mock_repo):
        mock_repo.list_notifications = AsyncMock(return_value=[])
        await service.list_notifications("u1", skip=10, limit=5)
        mock_repo.list_notifications.assert_awaited_once_with("u1", 10, 5)

    @pytest.mark.asyncio
    async def test_defaults_for_skip_and_limit(self, mock_repo):
        mock_repo.list_notifications = AsyncMock(return_value=[])
        await service.list_notifications("u1")
        mock_repo.list_notifications.assert_awaited_once_with("u1", 0, 50)


class TestMarkRead:
    @pytest.mark.asyncio
    async def test_marks_read_and_returns_response(self, mock_repo):
        mock_repo.mark_read = AsyncMock(return_value=_fake_notification(is_read=True))
        result = await service.mark_read("notif-1")
        assert result["id"] == "notif-1"
        assert result["is_read"] is True
        mock_repo.mark_read.assert_awaited_once_with("notif-1")

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mock_repo):
        mock_repo.mark_read = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="Notification not found"):
            await service.mark_read("nonexistent")


class TestResponseFormat:
    @pytest.mark.asyncio
    async def test_response_contains_all_expected_keys(self, mock_repo):
        mock_repo.create_notification = AsyncMock(return_value=_fake_notification())
        result = await service.create_notification("u1", "test", {})
        assert set(result.keys()) == {"id", "user_id", "type", "data", "is_read", "created_at"}

    @pytest.mark.asyncio
    async def test_missing_created_at_defaults_to_empty_string(self, mock_repo):
        notif = _fake_notification()
        del notif["created_at"]
        mock_repo.create_notification = AsyncMock(return_value=notif)
        result = await service.create_notification("u1", "test", {})
        assert result["created_at"] == ""
