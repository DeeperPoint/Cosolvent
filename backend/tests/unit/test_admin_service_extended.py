"""Extended tests for admin service — covers methods not in test_admin_service.py."""

from __future__ import annotations

from types import SimpleNamespace
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
def mock_profiles_service():
    with patch("app.modules.admin.service.profiles_service") as mock:
        yield mock


@pytest.fixture
def mock_ai_service():
    with patch("app.modules.admin.service.ai_service") as mock:
        yield mock


def _fake_config():
    return SimpleNamespace(
        marketplace=SimpleNamespace(
            name="TestMarket",
            industry="agriculture",
            model_dump=lambda: {"name": "TestMarket", "industry": "agriculture"},
        ),
        participant_types=[
            SimpleNamespace(model_dump=lambda: {"slug": "producer", "label": "Producer"}),
        ],
        communication=SimpleNamespace(
            conversation_rules=[
                SimpleNamespace(model_dump=lambda: {"initiator": "buyer", "receiver": "producer"}),
            ]
        ),
        discovery=SimpleNamespace(model_dump=lambda: {"vector_search_enabled": True}),
        type_slugs=lambda: ["producer", "buyer"],
    )


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_includes_marketplace_info(self, mock_repo):
        mock_repo.get_dashboard_stats = AsyncMock(return_value={"users": 10, "profiles": 5})
        result = await service.get_dashboard(_fake_config())
        assert result["marketplace"]["name"] == "TestMarket"
        assert result["marketplace"]["participant_types"] == ["producer", "buyer"]
        assert result["users"] == 10


class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_serialized_list(self, mock_repo):
        mock_repo.list_users = AsyncMock(
            return_value=[
                {"_id": "u1", "email": "a@example.com"},
                {"_id": "u2", "email": "b@example.com"},
            ]
        )
        result = await service.list_users()
        assert len(result) == 2
        assert result[0]["id"] == "u1"
        assert result[1]["id"] == "u2"

    @pytest.mark.asyncio
    async def test_passes_skip_and_limit(self, mock_repo):
        mock_repo.list_users = AsyncMock(return_value=[])
        await service.list_users(skip=5, limit=10)
        mock_repo.list_users.assert_awaited_once_with(5, 10)


class TestListApplications:
    @pytest.mark.asyncio
    async def test_list_all(self, mock_profiles_repo):
        mock_profiles_repo.list_applications = AsyncMock(
            return_value=[{"_id": "app1", "status": "pending"}]
        )
        result = await service.list_applications()
        assert len(result) == 1
        assert result[0]["id"] == "app1"

    @pytest.mark.asyncio
    async def test_list_by_status(self, mock_profiles_repo):
        mock_profiles_repo.list_applications = AsyncMock(return_value=[])
        await service.list_applications(status="pending")
        mock_profiles_repo.list_applications.assert_awaited_once_with("pending")


class TestRejectApplication:
    @pytest.mark.asyncio
    async def test_delegates_to_profiles_service(self, mock_profiles_service):
        mock_profiles_service.reject_application = AsyncMock(
            return_value={"status": "rejected", "feedback": "Incomplete"}
        )
        result = await service.reject_application("app1", "Incomplete")
        assert result["status"] == "rejected"
        mock_profiles_service.reject_application.assert_awaited_once_with("app1", "Incomplete")

    @pytest.mark.asyncio
    async def test_default_feedback_is_empty_string(self, mock_profiles_service):
        mock_profiles_service.reject_application = AsyncMock(
            return_value={"status": "rejected", "feedback": ""}
        )
        await service.reject_application("app1")
        mock_profiles_service.reject_application.assert_awaited_once_with("app1", "")


class TestGetConfigSummary:
    @pytest.mark.asyncio
    async def test_returns_structured_config(self):
        result = await service.get_config_summary(_fake_config())
        assert result["marketplace"]["name"] == "TestMarket"
        assert len(result["participant_types"]) == 1
        assert len(result["communication_rules"]) == 1
        assert result["discovery"]["vector_search_enabled"] is True


class TestUpdateProfileStatus:
    @pytest.mark.asyncio
    async def test_updates_status(self, mock_profiles_repo):
        mock_profiles_repo.update_profile = AsyncMock(
            return_value={"_id": "p1", "status": "suspended"}
        )
        result = await service.update_profile_status("p1", "suspended")
        assert result["id"] == "p1"
        assert result["status"] == "suspended"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_profiles_repo):
        mock_profiles_repo.update_profile = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.update_profile_status("nonexistent", "suspended")


class TestConversationMessages:
    @pytest.mark.asyncio
    async def test_returns_serialized_messages(self, mock_repo):
        mock_repo.get_conversation_messages = AsyncMock(
            return_value=[
                {"_id": "m1", "body": "Hello"},
                {"_id": "m2", "body": "World"},
            ]
        )
        result = await service.get_conversation_messages("c1")
        assert len(result) == 2
        assert result[0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_passes_pagination(self, mock_repo):
        mock_repo.get_conversation_messages = AsyncMock(return_value=[])
        await service.get_conversation_messages("c1", skip=5, limit=10)
        mock_repo.get_conversation_messages.assert_awaited_once_with("c1", 5, 10)


class TestLLMDelegation:
    @pytest.mark.asyncio
    async def test_get_llm_settings(self, mock_ai_service):
        mock_ai_service.get_llm_settings = AsyncMock(return_value={"model": "gpt-4"})
        result = await service.get_llm_settings()
        assert result["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_update_llm_settings(self, mock_ai_service):
        mock_ai_service.update_llm_settings = AsyncMock(return_value={"model": "gpt-4o"})
        result = await service.update_llm_settings({"model": "gpt-4o"})
        assert result["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_get_models(self, mock_ai_service):
        mock_ai_service.get_models = AsyncMock(return_value=[{"id": "gpt-4"}])
        result = await service.get_models()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_prompts(self, mock_ai_service):
        mock_ai_service.list_prompts = AsyncMock(return_value=[{"intent": "greeting"}])
        result = await service.list_prompts()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_update_prompt(self, mock_ai_service):
        mock_ai_service.update_prompt = AsyncMock(return_value={"intent": "greeting", "template": "Hi"})
        result = await service.update_prompt("greeting", "Hi")
        assert result["template"] == "Hi"

    @pytest.mark.asyncio
    async def test_list_documents(self, mock_ai_service):
        mock_ai_service.list_documents = AsyncMock(return_value=[{"id": "d1"}])
        result = await service.list_documents()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_delete_document(self, mock_ai_service):
        mock_ai_service.delete_document = AsyncMock(return_value=None)
        await service.delete_document("d1")
        mock_ai_service.delete_document.assert_awaited_once_with("d1")


class TestUpdateFAQ:
    @pytest.mark.asyncio
    async def test_update_faq(self, mock_repo):
        mock_repo.update_faq = AsyncMock(
            return_value={"_id": "f1", "question": "Updated?", "answer": "Yes"}
        )
        result = await service.update_faq("f1", {"question": "Updated?"})
        assert result["id"] == "f1"
        assert result["question"] == "Updated?"

    @pytest.mark.asyncio
    async def test_update_faq_not_found(self, mock_repo):
        mock_repo.update_faq = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.update_faq("nonexistent", {"question": "?"})


class TestListFAQs:
    @pytest.mark.asyncio
    async def test_list_active_only(self, mock_repo):
        mock_repo.list_faqs = AsyncMock(return_value=[{"_id": "f1", "is_active": True}])
        result = await service.list_faqs(active_only=True)
        assert len(result) == 1
        mock_repo.list_faqs.assert_awaited_once_with(True)
