from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError
from app.core.marketplace_config import load_marketplace_config
from app.modules.files import service, storage

FIXTURES = Path(__file__).parent.parent / "test_config"


@pytest.fixture
def mock_repo():
    with patch("app.modules.files.service.repo") as mock:
        yield mock


@pytest.fixture
def mock_storage():
    with patch("app.modules.files.service.storage") as mock:
        yield mock


@pytest.fixture
def mock_profiles_repo():
    with patch("app.modules.files.service.profiles_repo") as mock:
        mock.get_draft = AsyncMock(return_value=None)
        mock.get_profile_by_id = AsyncMock(return_value=None)
        yield mock


@pytest.mark.asyncio
async def test_get_file_treats_invalid_privacy_as_private_and_blocks_non_owner(mock_repo, mock_storage):
    mock_repo.get_file = AsyncMock(
        return_value={
            "_id": "f1",
            "user_id": "owner",
            "filename": "doc.txt",
            "content_type": "text/plain",
            "privacy": "unexpected",
            "s3_key": "uploads/abc/doc.txt",
            "url": "https://example.com/doc.txt",
        }
    )
    mock_storage.generate_presigned_get_url = AsyncMock(return_value="https://signed")

    with pytest.raises(ForbiddenError, match="Access denied"):
        await service.get_file("f1", {"_id": "intruder", "role": "user"})

    mock_storage.generate_presigned_get_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_private_upload_requires_permission(mock_repo, mock_storage, mock_profiles_repo):
    config = load_marketplace_config(FIXTURES / "agriculture.yaml")
    mock_storage.upload_fileobj = AsyncMock()

    with pytest.raises(ForbiddenError, match="can_share_private_assets"):
        await service.upload_file_stream(
            user={"_id": "u2", "participant_type": "buyer", "role": "user"},
            config=config,
            file_obj=BytesIO(b"doc"),
            filename="doc.txt",
            content_type="text/plain",
            size_bytes=3,
            privacy="private",
        )

    mock_storage.upload_fileobj.assert_not_awaited()
    mock_profiles_repo.get_draft.assert_not_awaited()
    mock_profiles_repo.get_profile_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rolls_back_s3_on_metadata_failure(mock_repo, mock_storage, mock_profiles_repo):
    config = load_marketplace_config(FIXTURES / "agriculture.yaml")
    uploaded = storage.UploadedObject(
        key="uploads/abc/doc.txt",
        url="https://bucket.s3.us-east-1.amazonaws.com/uploads/abc/doc.txt",
    )
    mock_storage.upload_fileobj = AsyncMock(return_value=uploaded)
    mock_storage.delete_file = AsyncMock()
    mock_repo.create_file = AsyncMock(side_effect=RuntimeError("db write failed"))

    with pytest.raises(RuntimeError, match="db write failed"):
        await service.upload_file_stream(
            user={"_id": "u1", "participant_type": "producer", "role": "user"},
            config=config,
            file_obj=BytesIO(b"doc"),
            filename="doc.txt",
            content_type="text/plain",
            size_bytes=3,
            privacy="public",
        )

    mock_storage.delete_file.assert_awaited_once_with(s3_key=uploaded.key, url=uploaded.url)
    mock_profiles_repo.get_draft.assert_not_awaited()
    mock_profiles_repo.get_profile_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_file_private_owner_receives_presigned_url(mock_repo, mock_storage):
    mock_repo.get_file = AsyncMock(
        return_value={
            "_id": "f1",
            "user_id": "u1",
            "filename": "doc.txt",
            "content_type": "text/plain",
            "privacy": "private",
            "s3_key": "uploads/abc/doc.txt",
            "url": "https://bucket.s3.us-east-1.amazonaws.com/uploads/abc/doc.txt",
        }
    )
    mock_storage.is_safe_upload_key.return_value = True
    mock_storage.generate_presigned_get_url = AsyncMock(return_value="https://signed.example.com")

    result = await service.get_file("f1", {"_id": "u1", "role": "user"})

    assert result["url"] == "https://signed.example.com"
    mock_storage.generate_presigned_get_url.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_blocks_profile_attachment_for_non_owner(mock_repo, mock_storage, mock_profiles_repo):
    config = load_marketplace_config(FIXTURES / "agriculture.yaml")
    mock_profiles_repo.get_draft = AsyncMock(return_value={"_id": "d-other"})
    mock_profiles_repo.get_profile_by_id = AsyncMock(return_value={"_id": "p1", "user_id": "owner"})
    mock_storage.upload_fileobj = AsyncMock()

    with pytest.raises(ForbiddenError, match="Cannot attach file"):
        await service.upload_file_stream(
            user={"_id": "u1", "participant_type": "producer", "role": "user"},
            config=config,
            file_obj=BytesIO(b"doc"),
            filename="doc.txt",
            content_type="text/plain",
            size_bytes=3,
            privacy="public",
            profile_id="p1",
        )

    mock_storage.upload_fileobj.assert_not_awaited()
