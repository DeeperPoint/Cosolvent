"""Communication service: conversations and messages."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.permission_engine import can_initiate_conversation
from app.modules.communication import repository as repo


async def create_conversation(
    initiator: dict[str, Any],
    receiver_id: str,
    initial_message: str | None,
    config: MarketplaceConfig,
) -> dict[str, Any]:
    from app.modules.auth.repository import find_user_by_id

    receiver = await find_user_by_id(receiver_id)
    if not receiver:
        raise NotFoundError("Receiver not found")

    initiator_type = initiator.get("participant_type", "")
    receiver_type = receiver.get("participant_type", "")
    initiator_id = initiator["_id"]

    allowed, requires_approval = can_initiate_conversation(config, initiator_type, receiver_type)
    if not allowed:
        raise ForbiddenError(
            f"{initiator_type} cannot initiate conversations with {receiver_type}"
        )

    rule_key = f"{initiator_type}->{receiver_type}"
    status = "pending" if requires_approval else "active"

    participants = [
        {"user_id": initiator_id, "participant_type": initiator_type},
        {"user_id": receiver_id, "participant_type": receiver_type},
    ]

    conv = await repo.create_conversation(
        participants=participants,
        initiator_id=initiator_id,
        rule_key=rule_key,
        status=status,
    )

    if initial_message and status == "active":
        await repo.create_message(
            conversation_id=str(conv["_id"]),
            sender_id=initiator_id,
            content=initial_message,
        )

    from app.modules.notifications.service import create_notification
    await create_notification(
        user_id=receiver_id,
        notification_type="chat_request",
        data={"conversation_id": str(conv["_id"]), "initiator_id": initiator_id},
    )

    return _serialize(conv)


async def accept_conversation(conv_id: str, user: dict) -> dict[str, Any]:
    user_id = user["_id"]
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user_id)
    if conv["status"] != "pending":
        raise ConflictError(f"Conversation is already {conv['status']}")
    if conv["initiator_id"] == user_id:
        raise ForbiddenError("Initiator cannot accept their own request")

    updated = await repo.update_conversation_status_if_current(conv_id, "pending", "active")
    if not updated:
        raise ConflictError("Conversation is no longer pending")

    from app.modules.notifications.service import create_notification
    await create_notification(
        user_id=conv["initiator_id"],
        notification_type="chat_request_approved",
        data={"conversation_id": conv_id},
    )
    return _serialize(updated)


async def reject_conversation(conv_id: str, user: dict) -> dict[str, Any]:
    user_id = user["_id"]
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user_id)
    if conv["status"] != "pending":
        raise ConflictError(f"Conversation is already {conv['status']}")

    updated = await repo.update_conversation_status_if_current(conv_id, "pending", "rejected")
    if not updated:
        raise ConflictError("Conversation is no longer pending")

    from app.modules.notifications.service import create_notification
    await create_notification(
        user_id=conv["initiator_id"],
        notification_type="chat_request_declined",
        data={"conversation_id": conv_id},
    )
    return _serialize(updated)


async def close_conversation(conv_id: str, user: dict) -> dict[str, Any]:
    user_id = user["_id"]
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user_id)
    updated = await repo.update_conversation_status(conv_id, "closed")
    return _serialize(updated)


async def get_conversation(conv_id: str, user: dict) -> dict[str, Any]:
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user["_id"])
    return _serialize(conv)


async def list_conversations(user: dict) -> list[dict]:
    convs = await repo.list_conversations_for_user(user["_id"])
    return [_serialize(c) for c in convs]


async def send_message(
    conv_id: str,
    user: dict,
    content: str,
    content_type: str = "text",
) -> dict[str, Any]:
    sender_id = user["_id"]
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, sender_id)
    if conv["status"] != "active":
        raise ForbiddenError("Conversation is not active")

    msg = await repo.create_message(conv_id, sender_id, content, content_type)

    from app.modules.notifications.service import create_notification
    for p in conv["participants"]:
        if p["user_id"] != sender_id:
            await create_notification(
                user_id=p["user_id"],
                notification_type="new_message",
                data={"conversation_id": conv_id, "sender_id": sender_id},
            )

    return _serialize(msg)


async def edit_message(conv_id: str, msg_id: str, user: dict, content: str) -> dict[str, Any]:
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user["_id"])

    msg = await repo.get_message(msg_id)
    if not msg or msg.get("conversation_id") != conv_id:
        raise NotFoundError("Message not found")
    if msg["sender_id"] != user["_id"]:
        raise ForbiddenError("Can only edit own messages")
    updated = await repo.update_message_for_sender_in_conversation(
        msg_id,
        conv_id,
        user["_id"],
        content,
    )
    if not updated:
        raise NotFoundError("Message not found")
    return _serialize(updated)


async def delete_message(conv_id: str, msg_id: str, user: dict) -> None:
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user["_id"])

    msg = await repo.get_message(msg_id)
    if not msg or msg.get("conversation_id") != conv_id:
        raise NotFoundError("Message not found")
    if msg["sender_id"] != user["_id"]:
        raise ForbiddenError("Can only delete own messages")
    deleted = await repo.delete_message_for_sender_in_conversation(msg_id, conv_id, user["_id"])
    if not deleted:
        raise NotFoundError("Message not found")


async def list_messages(conv_id: str, user: dict, skip: int = 0, limit: int = 50) -> list[dict]:
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, user["_id"])
    msgs = await repo.list_messages(conv_id, skip, limit)
    return [_serialize(m) for m in msgs]


async def share_assets(conv_id: str, user: dict, asset_ids: list[str]) -> dict[str, Any]:
    sender_id = user["_id"]
    conv = await _get_conversation_or_404(conv_id)
    _assert_participant(conv, sender_id)
    if conv["status"] != "active":
        raise ForbiddenError("Conversation is not active")

    for asset_id in asset_ids:
        await repo.create_message(
            conversation_id=conv_id,
            sender_id=sender_id,
            content=asset_id,
            content_type="file",
        )
    return {"detail": f"Shared {len(asset_ids)} assets"}


async def _get_conversation_or_404(conv_id: str) -> dict:
    conv = await repo.get_conversation(conv_id)
    if not conv:
        raise NotFoundError("Conversation not found")
    return conv


def _assert_participant(conv: dict, user_id: str) -> None:
    participant_ids = [p["user_id"] for p in conv["participants"]]
    if user_id not in participant_ids:
        raise ForbiddenError("Not a participant in this conversation")


def _serialize(doc: dict) -> dict:
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
