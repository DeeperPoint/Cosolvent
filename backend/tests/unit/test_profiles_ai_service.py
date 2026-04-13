"""Tests for profile AI lifecycle in service layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.modules.profiles import service


@pytest.fixture
def mock_repo():
    with patch("app.modules.profiles.service.repo") as mock:
        yield mock


@pytest.fixture
def mock_generate():
    with patch("app.modules.profiles.service.generate_profile_content", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_enqueue():
    with patch("app.modules.profiles.service.enqueue_job", new_callable=AsyncMock) as mock:
        yield mock


def _config():
    class _Marketplace:
        description = "Test marketplace"
        name = "Test Market"

    class _Cfg:
        marketplace = _Marketplace()

    return _Cfg()


@pytest.mark.asyncio
async def test_ai_generate_profile_updates_draft(mock_repo, mock_generate, mock_enqueue):
    mock_repo.get_profile_by_id = AsyncMock(
        return_value={"_id": "p1", "user_id": "u1", "participant_type": "producer", "fields": {"farm": "x"}}
    )
    mock_repo.update_profile = AsyncMock(
        return_value={
            "_id": "p1",
            "ai_profile": None,
            "ai_profile_draft": "Generated summary",
            "ai_profile_status": "generated",
        }
    )
    mock_generate.return_value = "Generated summary"
    result = await service.ai_generate_profile("p1", {"_id": "u1", "role": "user"}, _config())
    assert result["status"] == "generated"
    assert result["ai_profile_draft"] == "Generated summary"


@pytest.mark.asyncio
async def test_ai_generate_profile_rejects_non_owner(mock_repo, mock_generate, mock_enqueue):
    mock_repo.get_profile_by_id = AsyncMock(
        return_value={"_id": "p1", "user_id": "owner", "participant_type": "producer", "fields": {}}
    )
    with pytest.raises(ForbiddenError):
        await service.ai_generate_profile("p1", {"_id": "other", "role": "user"}, _config())


@pytest.mark.asyncio
async def test_ai_approve_requires_draft(mock_repo, mock_enqueue):
    mock_repo.get_profile_by_id = AsyncMock(return_value={"_id": "p1", "ai_profile_draft": None})
    with pytest.raises(AppError):
        await service.ai_approve_profile("p1")


@pytest.mark.asyncio
async def test_ai_reject_not_found(mock_repo, mock_enqueue):
    mock_repo.get_profile_by_id = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await service.ai_reject_profile("missing")
