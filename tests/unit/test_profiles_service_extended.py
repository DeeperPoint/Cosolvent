"""Extended tests for profiles service — covers register, get_draft, update, reject."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.profiles import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _submit_config(
    *,
    requires_approval: bool = True,
    approval_type: str = "manual",
    profile_completeness_threshold: int = 80,
    document_upload_required: bool = False,
):
    onboarding = SimpleNamespace(
        requires_approval=requires_approval,
        approval_type=approval_type,
        profile_completeness_threshold=profile_completeness_threshold,
        document_upload_required=document_upload_required,
        welcome_email_on_approval=True,
    )
    return SimpleNamespace(
        onboarding={"producer": onboarding},
        marketplace=SimpleNamespace(name="Test Market"),
    )


@pytest.fixture
def mock_repo():
    with patch("app.modules.profiles.service.repo") as mock:
        yield mock


@pytest.fixture
def mock_files_repo():
    with patch("app.modules.profiles.service.files_repo") as mock:
        yield mock


@pytest.fixture
def mock_collection():
    collection = AsyncMock()
    collection.update_one = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    with patch("app.modules.profiles.service.get_collection", return_value=collection):
        yield collection


class TestRegister:
    @pytest.mark.asyncio
    async def test_creates_draft(self, mock_repo):
        mock_repo.get_draft = AsyncMock(return_value=None)
        mock_repo.get_profile_by_user = AsyncMock(return_value=None)
        mock_repo.upsert_draft = AsyncMock(
            return_value={
                "_id": "d1",
                "user_id": "u1",
                "participant_type": "producer",
                "status": "draft",
                "fields": {},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        result = await service.register({"_id": "u1", "participant_type": "producer"}, cfg)
        assert result["id"] == "d1"
        assert result["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_rejects_duplicate_draft(self, mock_repo):
        mock_repo.get_draft = AsyncMock(return_value={"_id": "d1"})
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        with pytest.raises(ConflictError, match="Draft already exists"):
            await service.register({"_id": "u1", "participant_type": "producer"}, cfg)

    @pytest.mark.asyncio
    async def test_rejects_existing_profile(self, mock_repo):
        mock_repo.get_draft = AsyncMock(return_value=None)
        mock_repo.get_profile_by_user = AsyncMock(return_value={"_id": "p1"})
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        with pytest.raises(ConflictError, match="Profile already exists"):
            await service.register({"_id": "u1", "participant_type": "producer"}, cfg)


class TestGetDraft:
    @pytest.mark.asyncio
    async def test_returns_draft(self, mock_repo):
        mock_repo.get_draft = AsyncMock(
            return_value={
                "_id": "d1",
                "user_id": "u1",
                "participant_type": "producer",
                "status": "draft",
                "fields": {"farm_name": "North Ridge"},
                "created_at": "",
                "updated_at": "",
            }
        )
        result = await service.get_draft({"_id": "u1"})
        assert result["id"] == "d1"
        assert result["fields"]["farm_name"] == "North Ridge"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_draft = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="No draft found"):
            await service.get_draft({"_id": "u1"})


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_rejects_non_owner(self, mock_repo):
        mock_repo.get_profile_by_id = AsyncMock(
            return_value={
                "_id": "p1",
                "user_id": "owner",
                "participant_type": "producer",
                "fields": {},
            }
        )
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        with pytest.raises(ForbiddenError, match="Not your profile"):
            await service.update_profile(
                "p1",
                {"_id": "other", "role": "user"},
                {"farm_name": "New"},
                cfg,
            )

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_profile_by_id = AsyncMock(return_value=None)
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        with pytest.raises(NotFoundError, match="Profile not found"):
            await service.update_profile(
                "nonexistent",
                {"_id": "u1", "role": "user"},
                {},
                cfg,
            )


class TestRejectApplication:
    @pytest.mark.asyncio
    async def test_rejects_pending_app(self, mock_repo):
        mock_repo.get_application = AsyncMock(
            return_value={"_id": "app1", "status": "pending", "user_id": "u1"}
        )
        mock_repo.update_application = AsyncMock()
        result = await service.reject_application("app1", "Incomplete docs")
        assert result["status"] == "rejected"
        assert result["feedback"] == "Incomplete docs"

    @pytest.mark.asyncio
    async def test_rejects_non_pending(self, mock_repo):
        mock_repo.get_application = AsyncMock(
            return_value={"_id": "app1", "status": "approved"}
        )
        with pytest.raises(AppError, match="not pending"):
            await service.reject_application("app1")

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_application = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="Application not found"):
            await service.reject_application("nonexistent")


class TestGetMyProfile:
    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_profile_by_user = AsyncMock(return_value=None)
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        with pytest.raises(NotFoundError, match="No profile found"):
            await service.get_my_profile({"_id": "u1"}, cfg)


class TestSubmitDraftAutoApprove:
    @pytest.mark.asyncio
    async def test_auto_approve_creates_profile_directly(self, mock_repo, mock_files_repo, mock_collection):
        mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": {"farm_name": "Ridge"}})
        mock_repo.get_profile_by_user = AsyncMock(return_value=None)
        mock_repo.get_pending_application_by_user = AsyncMock(return_value=None)
        mock_repo.create_profile = AsyncMock(return_value={"_id": "p1"})
        mock_repo.delete_draft = AsyncMock()

        with patch("app.modules.profiles.service.compute_completeness", return_value=100), patch(
            "app.modules.profiles.service._queue_profile_index", new=AsyncMock()
        ), patch(
            "app.modules.profiles.service._queue_welcome_email", new=AsyncMock()
        ):
            result = await service.submit_draft(
                {"_id": "u1", "participant_type": "producer", "email": "test@example.com"},
                _submit_config(requires_approval=False),
            )

        assert result["status"] == "active"
        assert result["profile_id"] == "p1"
        mock_repo.delete_draft.assert_awaited_once_with("u1")

    @pytest.mark.asyncio
    async def test_below_completeness_threshold_raises(self, mock_repo, mock_files_repo):
        mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": {}})
        mock_repo.get_profile_by_user = AsyncMock(return_value=None)
        mock_repo.get_pending_application_by_user = AsyncMock(return_value=None)

        with patch("app.modules.profiles.service.compute_completeness", return_value=50):
            with pytest.raises(AppError, match="completeness"):
                await service.submit_draft(
                    {"_id": "u1", "participant_type": "producer"},
                    _submit_config(profile_completeness_threshold=80),
                )


class TestAIApproveProfile:
    @pytest.mark.asyncio
    async def test_approves_draft(self, mock_repo):
        mock_repo.get_profile_by_id = AsyncMock(
            return_value={"_id": "p1", "ai_profile_draft": "Generated summary"}
        )
        mock_repo.update_profile = AsyncMock(
            return_value={
                "_id": "p1",
                "ai_profile": "Generated summary",
                "ai_profile_draft": "Generated summary",
                "ai_profile_status": "approved",
                "ai_profile_updated_at": "2026-01-15T12:00:00+00:00",
            }
        )
        result = await service.ai_approve_profile("p1")
        assert result["status"] == "approved"
        assert result["ai_profile"] == "Generated summary"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_profile_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.ai_approve_profile("nonexistent")


class TestAIRejectProfile:
    @pytest.mark.asyncio
    async def test_rejects_and_clears_draft(self, mock_repo):
        mock_repo.get_profile_by_id = AsyncMock(
            return_value={"_id": "p1", "ai_profile_draft": "Old draft"}
        )
        mock_repo.update_profile = AsyncMock(
            return_value={
                "_id": "p1",
                "ai_profile": None,
                "ai_profile_draft": None,
                "ai_profile_status": "rejected",
                "ai_profile_updated_at": "2026-01-15T12:00:00+00:00",
            }
        )
        result = await service.ai_reject_profile("p1")
        assert result["status"] == "rejected"
        assert result["ai_profile_draft"] is None
