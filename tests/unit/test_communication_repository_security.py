from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.communication import repository as repo


@pytest.mark.asyncio
async def test_update_message_for_sender_in_conversation_uses_scoped_filter():
    messages = AsyncMock()
    messages.find_one_and_update = AsyncMock(return_value={"_id": "m1"})

    with patch("app.modules.communication.repository.get_collection", return_value=messages):
        result = await repo.update_message_for_sender_in_conversation("m1", "c1", "u1", "updated")

    assert result == {"_id": "m1"}
    call = messages.find_one_and_update.await_args
    assert call.args[0] == {"_id": "m1", "conversation_id": "c1", "sender_id": "u1"}


@pytest.mark.asyncio
async def test_update_message_for_sender_in_conversation_returns_none_on_miss():
    messages = AsyncMock()
    messages.find_one_and_update = AsyncMock(return_value=None)

    with patch("app.modules.communication.repository.get_collection", return_value=messages):
        result = await repo.update_message_for_sender_in_conversation("m1", "c1", "u1", "updated")

    assert result is None


@pytest.mark.asyncio
async def test_delete_message_for_sender_in_conversation_returns_false_on_miss():
    messages = AsyncMock()
    messages.delete_one = AsyncMock(return_value=type("DeleteResult", (), {"deleted_count": 0})())

    with patch("app.modules.communication.repository.get_collection", return_value=messages):
        deleted = await repo.delete_message_for_sender_in_conversation("m1", "c1", "u1")

    assert deleted is False
    messages.delete_one.assert_awaited_once_with({"_id": "m1", "conversation_id": "c1", "sender_id": "u1"})


@pytest.mark.asyncio
async def test_update_conversation_status_if_current_scopes_expected_status():
    conversations = AsyncMock()
    conversations.find_one_and_update = AsyncMock(return_value={"_id": "c1", "status": "active"})

    with patch("app.modules.communication.repository.get_collection", return_value=conversations):
        result = await repo.update_conversation_status_if_current("c1", "pending", "active")

    assert result == {"_id": "c1", "status": "active"}
    call = conversations.find_one_and_update.await_args
    assert call.args[0] == {"_id": "c1", "status": "pending"}
