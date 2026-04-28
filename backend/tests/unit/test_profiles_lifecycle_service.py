from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppError, ConflictError, NotFoundError
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


@pytest.mark.asyncio
async def test_submit_draft_returns_existing_pending_application(mock_repo, mock_files_repo):
    mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": {"farm_name": "North Ridge"}})
    mock_repo.get_profile_by_user = AsyncMock(return_value=None)
    mock_repo.get_pending_application_by_user = AsyncMock(return_value={"_id": "app-1"})
    mock_repo.create_application = AsyncMock()
    mock_files_repo.count_files_for_profile_owner = AsyncMock()

    with patch("app.modules.profiles.service.compute_completeness", return_value=100):
        result = await service.submit_draft(
            {"_id": "u1", "participant_type": "producer"},
            _submit_config(),
        )

    assert result == {"status": "pending_review", "application_id": "app-1"}
    mock_repo.create_application.assert_not_called()
    mock_files_repo.count_files_for_profile_owner.assert_not_called()


@pytest.mark.asyncio
async def test_submit_draft_rejects_when_profile_already_exists(mock_repo, mock_files_repo):
    mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": {"farm_name": "North Ridge"}})
    mock_repo.get_profile_by_user = AsyncMock(return_value={"_id": "p1"})
    mock_repo.get_pending_application_by_user = AsyncMock()

    with patch("app.modules.profiles.service.compute_completeness", return_value=100):
        with pytest.raises(ConflictError, match="Profile already exists"):
            await service.submit_draft(
                {"_id": "u1", "participant_type": "producer"},
                _submit_config(),
            )

    mock_repo.get_pending_application_by_user.assert_not_called()
    mock_files_repo.count_files_for_profile_owner.assert_not_called()


@pytest.mark.asyncio
async def test_submit_draft_requires_onboarding_document_when_configured(mock_repo, mock_files_repo):
    mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": {"farm_name": "North Ridge"}})
    mock_repo.get_profile_by_user = AsyncMock(return_value=None)
    mock_repo.get_pending_application_by_user = AsyncMock(return_value=None)
    mock_repo.create_application = AsyncMock()
    mock_files_repo.count_files_for_profile_owner = AsyncMock(return_value=0)

    with patch("app.modules.profiles.service.compute_completeness", return_value=100):
        with pytest.raises(AppError) as exc:
            await service.submit_draft(
                {"_id": "u1", "participant_type": "producer"},
                _submit_config(document_upload_required=True),
            )

    assert exc.value.status_code == 422
    mock_repo.create_application.assert_not_called()


@pytest.mark.asyncio
async def test_submit_draft_creates_application_with_submission_snapshot(mock_repo, mock_files_repo):
    draft_fields = {"farm_name": "North Ridge"}
    mock_repo.get_draft = AsyncMock(return_value={"_id": "d1", "fields": draft_fields})
    mock_repo.get_profile_by_user = AsyncMock(return_value=None)
    mock_repo.get_pending_application_by_user = AsyncMock(return_value=None)
    mock_repo.create_application = AsyncMock(return_value={"_id": "app-1"})
    mock_files_repo.count_files_for_profile_owner = AsyncMock(return_value=1)

    with patch("app.modules.profiles.service.compute_completeness", return_value=88):
        result = await service.submit_draft(
            {"_id": "u1", "participant_type": "producer"},
            _submit_config(document_upload_required=True),
        )

    assert result == {"status": "pending_review", "application_id": "app-1"}
    mock_repo.create_application.assert_awaited_once_with(
        participant_type="producer",
        submitted_fields={"farm_name": "North Ridge"},
        submitted_completeness=88,
        user_id="u1",
        draft_id="d1",
    )


@pytest.mark.asyncio
async def test_submit_application_without_account_stores_pending_only(mock_repo):
    mock_repo.get_pending_application_by_email = AsyncMock(return_value=None)
    mock_repo.create_application = AsyncMock(return_value={"_id": "app-new"})
    with patch("app.modules.profiles.service.auth_repo") as mock_auth:
        mock_auth.find_user_by_email = AsyncMock(return_value=None)
        with patch(
            "app.modules.profiles.service.validate_profile_fields",
            return_value={"farm_name": "North Ridge"},
        ):
            with patch("app.modules.profiles.service.compute_completeness", return_value=100):
                result = await service.submit_application_without_account(
                    "applicant@example.com",
                    "producer",
                    _submit_config(),
                    {"farm_name": "North Ridge"},
                )

    assert result == {"status": "pending_review", "application_id": "app-new"}
    mock_repo.create_application.assert_awaited_once_with(
        participant_type="producer",
        submitted_fields={"farm_name": "North Ridge"},
        submitted_completeness=100,
        applicant_email="applicant@example.com",
    )


@pytest.mark.asyncio
async def test_approve_application_pre_account_creates_user_and_profile(mock_repo, mock_collection):
    mock_repo.get_application = AsyncMock(
        return_value={
            "_id": "app-1",
            "status": "pending",
            "user_id": None,
            "applicant_email": "new@example.com",
            "participant_type": "producer",
            "submitted_fields": {"farm_name": "Submitted"},
            "submitted_completeness": 90,
        }
    )
    mock_repo.create_profile = AsyncMock(return_value={"_id": "p1"})
    mock_repo.update_application = AsyncMock()
    mock_collection.update_one = AsyncMock()

    with patch("app.modules.profiles.service.auth_repo") as mock_auth:
        mock_auth.find_user_by_email = AsyncMock(return_value=None)
        mock_auth.create_user = AsyncMock(
            return_value={"_id": "u-new", "email": "new@example.com"}
        )
        with patch("app.modules.profiles.service.get_marketplace_config") as mock_cfg:
            mock_cfg.return_value = SimpleNamespace(marketplace=SimpleNamespace(name="Test Market"))
            with patch("app.modules.profiles.service._queue_profile_index", new=AsyncMock()), patch(
                "app.modules.profiles.service._queue_welcome_email_with_password", new=AsyncMock()
            ), patch(
                "app.modules.profiles.service.files_repo.reassign_application_files_to_profile",
                new=AsyncMock(),
            ):
                result = await service.approve_application("app-1")

    assert result["status"] == "approved"
    assert result["profile_id"] == "p1"
    assert result["applicant_email"] == "new@example.com"
    assert isinstance(result.get("temporary_password"), str) and result["temporary_password"]
    mock_auth.create_user.assert_awaited_once()
    mock_repo.create_profile.assert_awaited_once_with(
        user_id="u-new",
        participant_type="producer",
        fields={"farm_name": "Submitted"},
        status="active",
        completeness=90,
    )


@pytest.mark.asyncio
async def test_approve_application_uses_submitted_snapshot(mock_repo, mock_collection):
    mock_repo.get_application = AsyncMock(
        return_value={
            "_id": "app-1",
            "status": "pending",
            "user_id": "u1",
            "participant_type": "producer",
            "submitted_fields": {"farm_name": "Submitted Snapshot"},
            "submitted_completeness": 72,
        }
    )
    mock_repo.get_draft = AsyncMock()
    mock_repo.create_profile = AsyncMock(return_value={"_id": "p1"})
    mock_repo.delete_draft = AsyncMock()
    mock_repo.update_application = AsyncMock()
    mock_collection.find_one.return_value = {"email": "owner@example.com"}

    mkt_cfg = SimpleNamespace(
        marketplace=SimpleNamespace(name="Test Market"),
        onboarding={"producer": SimpleNamespace(welcome_email_on_approval=True)},
    )
    with patch("app.modules.profiles.service.get_marketplace_config", return_value=mkt_cfg), patch(
        "app.modules.profiles.service._queue_profile_index", new=AsyncMock()
    ), patch(
        "app.modules.profiles.service._ensure_password_and_notify_approval",
        new=AsyncMock(),
    ):
        result = await service.approve_application("app-1")

    assert result == {"status": "approved", "profile_id": "p1"}
    mock_repo.create_profile.assert_awaited_once_with(
        user_id="u1",
        participant_type="producer",
        fields={"farm_name": "Submitted Snapshot"},
        status="active",
        completeness=72,
    )
    mock_repo.get_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_application_legacy_falls_back_to_draft(mock_repo, mock_collection):
    mock_repo.get_application = AsyncMock(
        return_value={
            "_id": "app-1",
            "status": "pending",
            "user_id": "u1",
            "participant_type": "producer",
        }
    )
    mock_repo.get_draft = AsyncMock(return_value={"fields": {"farm_name": "Legacy Draft"}})
    mock_repo.create_profile = AsyncMock(return_value={"_id": "p1"})
    mock_repo.delete_draft = AsyncMock()
    mock_repo.update_application = AsyncMock()
    mock_collection.find_one.return_value = None

    mkt_cfg = SimpleNamespace(
        marketplace=SimpleNamespace(name="Test Market"),
        onboarding={"producer": SimpleNamespace(welcome_email_on_approval=True)},
    )
    with patch("app.modules.profiles.service.get_marketplace_config", return_value=mkt_cfg), patch(
        "app.modules.profiles.service._queue_profile_index", new=AsyncMock()
    ), patch(
        "app.modules.profiles.service._ensure_password_and_notify_approval",
        new=AsyncMock(),
    ):
        result = await service.approve_application("app-1")

    assert result == {"status": "approved", "profile_id": "p1"}
    mock_repo.create_profile.assert_awaited_once_with(
        user_id="u1",
        participant_type="producer",
        fields={"farm_name": "Legacy Draft"},
        status="active",
        completeness=100,
    )


@pytest.mark.asyncio
async def test_get_profile_hides_non_active_from_non_owner(mock_repo):
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    mock_repo.get_profile_by_id = AsyncMock(
        return_value={
            "_id": "p1",
            "user_id": "owner",
            "participant_type": "producer",
            "status": "suspended",
            "fields": {"farm_name": "North Ridge"},
        }
    )
    with pytest.raises(NotFoundError, match="Profile not found"):
        await service.get_profile(
            "p1",
            "producer",
            cfg,
            current_user={"_id": "viewer", "role": "user"},
        )


@pytest.mark.asyncio
async def test_get_profile_redacts_ai_fields_for_non_owner(mock_repo):
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    mock_repo.get_profile_by_id = AsyncMock(
        return_value={
            "_id": "p1",
            "user_id": "owner",
            "participant_type": "producer",
            "status": "active",
            "fields": {"farm_name": "North Ridge", "country": "Canada"},
            "ai_profile": "approved AI summary",
            "ai_profile_draft": "draft AI summary",
            "ai_profile_status": "approved",
        }
    )

    result = await service.get_profile(
        "p1",
        "producer",
        cfg,
        current_user={"_id": "viewer", "role": "user"},
    )
    assert result["ai_profile"] is None
    assert result["ai_profile_draft"] is None
