"""Tests for admin service layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.modules.admin import service


@pytest.fixture
def mock_repo():
    with patch("app.modules.admin.service.repo") as mock:
        yield mock


@pytest.fixture
def mock_profiles_repo():
    with patch("app.modules.admin.service.profiles_repo") as mock:
        yield mock


@pytest.fixture
def mock_ai_service():
    with patch("app.modules.admin.service.ai_service") as mock:
        yield mock


def _fake_user(user_id="abc123"):
    return {"_id": user_id, "email": "test@example.com", "role": "user"}


def _fake_faq(faq_id="faq123"):
    return {"_id": faq_id, "question": "What?", "answer": "That.", "is_active": True}


def _fake_profile(profile_id="prof123"):
    return {"_id": profile_id, "user_id": "u1", "status": "active", "fields": {}}


class TestGetUser:
    @pytest.mark.asyncio
    async def test_found(self, mock_repo):
        mock_repo.get_user = AsyncMock(return_value=_fake_user())
        result = await service.get_user("abc123")
        assert result["id"] == "abc123"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_user = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.get_user("nonexistent")


class TestUpdateUserRole:
    @pytest.mark.asyncio
    async def test_success(self, mock_repo):
        mock_repo.update_user_role = AsyncMock(return_value=_fake_user())
        result = await service.update_user_role("abc123", "admin")
        assert result["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.update_user_role = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.update_user_role("nonexistent", "admin")


class TestDeactivateActivateUser:
    @pytest.mark.asyncio
    async def test_deactivate(self, mock_repo):
        mock_repo.deactivate_user = AsyncMock(return_value=_fake_user())
        result = await service.deactivate_user("abc123")
        assert result["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_deactivate_not_found(self, mock_repo):
        mock_repo.deactivate_user = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.deactivate_user("nonexistent")

    @pytest.mark.asyncio
    async def test_activate(self, mock_repo):
        mock_repo.activate_user = AsyncMock(return_value=_fake_user())
        result = await service.activate_user("abc123")
        assert result["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_activate_not_found(self, mock_repo):
        mock_repo.activate_user = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.activate_user("nonexistent")


class TestFAQ:
    @pytest.mark.asyncio
    async def test_create_faq(self, mock_repo):
        mock_repo.create_faq = AsyncMock(return_value=_fake_faq())
        result = await service.create_faq({"question": "What?", "answer": "That."})
        assert result["id"] == "faq123"
        assert result["question"] == "What?"

    @pytest.mark.asyncio
    async def test_list_faqs(self, mock_repo):
        mock_repo.list_faqs = AsyncMock(return_value=[_fake_faq(), _fake_faq("faq456")])
        result = await service.list_faqs()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_delete_faq(self, mock_repo):
        mock_repo.get_faq = AsyncMock(return_value=_fake_faq())
        mock_repo.delete_faq = AsyncMock(return_value=True)
        result = await service.delete_faq("faq123")
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_faq_not_found(self, mock_repo):
        mock_repo.get_faq = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.delete_faq("nonexistent")

    @pytest.mark.asyncio
    async def test_get_faq(self, mock_repo):
        mock_repo.get_faq = AsyncMock(return_value=_fake_faq())
        result = await service.get_faq("faq123")
        assert result["id"] == "faq123"

    @pytest.mark.asyncio
    async def test_get_faq_not_found(self, mock_repo):
        mock_repo.get_faq = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.get_faq("nonexistent")


class TestProfileFull:
    @pytest.mark.asyncio
    async def test_get_profile_full(self, mock_profiles_repo):
        mock_profiles_repo.get_profile_by_id = AsyncMock(return_value=_fake_profile())
        result = await service.get_profile_full("prof123")
        assert result["id"] == "prof123"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_profile_full_not_found(self, mock_profiles_repo):
        mock_profiles_repo.get_profile_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.get_profile_full("nonexistent")


class TestConversationOversight:
    @pytest.mark.asyncio
    async def test_list_all_conversations(self, mock_repo):
        mock_repo.list_all_conversations = AsyncMock(return_value=[
            {"_id": "c1", "status": "active"},
            {"_id": "c2", "status": "closed"},
        ])
        result = await service.list_all_conversations()
        assert len(result) == 2
        assert result[0]["id"] == "c1"
