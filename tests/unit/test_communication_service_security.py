from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.communication import service

FIXTURES = Path(__file__).parent.parent / "test_config"


@pytest.fixture
def mock_repo():
    with patch("app.modules.communication.service.repo") as mock:
        yield mock


def _conversation(conv_id: str = "conv-1") -> dict:
    return {
        "_id": conv_id,
        "status": "active",
        "initiator_id": "u1",
        "participants": [{"user_id": "u1"}, {"user_id": "u2"}],
    }


def _config():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


@pytest.mark.asyncio
async def test_edit_message_blocks_non_participant(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u1"})

    with pytest.raises(ForbiddenError, match="Not a participant"):
        await service.edit_message("conv-1", "m1", {"_id": "u3"}, "new")

    mock_repo.get_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_message_returns_404_on_conversation_mismatch(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m2", "conversation_id": "conv-2", "sender_id": "u1"})

    with pytest.raises(NotFoundError, match="Message not found"):
        await service.edit_message("conv-1", "m2", {"_id": "u1"}, "new")


@pytest.mark.asyncio
async def test_edit_message_blocks_non_owner_participant(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u2"})

    with pytest.raises(ForbiddenError, match="edit own messages"):
        await service.edit_message("conv-1", "m1", {"_id": "u1"}, "new")


@pytest.mark.asyncio
async def test_edit_message_handles_conditional_update_race_as_not_found(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u1"})
    mock_repo.update_message_for_sender_in_conversation = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError, match="Message not found"):
        await service.edit_message("conv-1", "m1", {"_id": "u1"}, "new")


@pytest.mark.asyncio
async def test_delete_message_blocks_non_participant(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u1"})

    with pytest.raises(ForbiddenError, match="Not a participant"):
        await service.delete_message("conv-1", "m1", {"_id": "u3"})

    mock_repo.get_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_message_returns_404_on_conversation_mismatch(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m2", "conversation_id": "conv-2", "sender_id": "u1"})

    with pytest.raises(NotFoundError, match="Message not found"):
        await service.delete_message("conv-1", "m2", {"_id": "u1"})


@pytest.mark.asyncio
async def test_delete_message_blocks_non_owner_participant(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u2"})

    with pytest.raises(ForbiddenError, match="delete own messages"):
        await service.delete_message("conv-1", "m1", {"_id": "u1"})


@pytest.mark.asyncio
async def test_delete_message_handles_conditional_delete_race_as_not_found(mock_repo):
    mock_repo.get_conversation = AsyncMock(return_value=_conversation())
    mock_repo.get_message = AsyncMock(return_value={"_id": "m1", "conversation_id": "conv-1", "sender_id": "u1"})
    mock_repo.delete_message_for_sender_in_conversation = AsyncMock(return_value=False)

    with pytest.raises(NotFoundError, match="Message not found"):
        await service.delete_message("conv-1", "m1", {"_id": "u1"})


@pytest.mark.asyncio
async def test_accept_conversation_conflict_when_conditional_update_misses(mock_repo):
    conv = _conversation()
    conv["status"] = "pending"
    conv["initiator_id"] = "u1"
    mock_repo.get_conversation = AsyncMock(return_value=conv)
    mock_repo.update_conversation_status_if_current = AsyncMock(return_value=None)

    with pytest.raises(ConflictError, match="no longer pending"):
        await service.accept_conversation("conv-1", {"_id": "u2"})


@pytest.mark.asyncio
async def test_reject_conversation_conflict_when_conditional_update_misses(mock_repo):
    conv = _conversation()
    conv["status"] = "pending"
    conv["initiator_id"] = "u1"
    mock_repo.get_conversation = AsyncMock(return_value=conv)
    mock_repo.update_conversation_status_if_current = AsyncMock(return_value=None)

    with pytest.raises(ConflictError, match="no longer pending"):
        await service.reject_conversation("conv-1", {"_id": "u2"})


@pytest.mark.asyncio
async def test_create_conversation_blocks_non_onboarded_initiator(mock_repo):
    with patch(
        "app.modules.auth.repository.find_user_by_id",
        new=AsyncMock(
            return_value={"_id": "u2", "participant_type": "producer", "role": "user", "has_onboarded": True}
        ),
    ):
        with pytest.raises(ForbiddenError, match="Complete onboarding"):
            await service.create_conversation(
                {"_id": "u1", "participant_type": "buyer", "role": "user", "has_onboarded": False},
                "u2",
                "hello",
                _config(),
            )
    mock_repo.create_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_create_conversation_blocks_non_onboarded_receiver(mock_repo):
    with patch(
        "app.modules.auth.repository.find_user_by_id",
        new=AsyncMock(
            return_value={"_id": "u2", "participant_type": "producer", "role": "user", "has_onboarded": False}
        ),
    ):
        with pytest.raises(ForbiddenError, match="has not completed onboarding"):
            await service.create_conversation(
                {"_id": "u1", "participant_type": "buyer", "role": "user", "has_onboarded": True},
                "u2",
                "hello",
                _config(),
            )
    mock_repo.create_conversation.assert_not_called()
