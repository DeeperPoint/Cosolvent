"""Communication service: conversations and messages."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.permission_engine import can_initiate_conversation, has_completed_required_onboarding
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

    if not has_completed_required_onboarding(config, initiator):
        raise ForbiddenError("Complete onboarding before initiating conversations")
    if not has_completed_required_onboarding(config, receiver):
        raise ForbiddenError("Cannot start a conversation with a user who has not completed onboarding")

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
    serialized = _serialize(conv)
    await _enrich_participants([serialized])
    return serialized


async def list_conversations(user: dict) -> list[dict]:
    convs = await repo.list_conversations_for_user(user["_id"])
    serialized = [_serialize(c) for c in convs]
    await _enrich_participants(serialized)
    return serialized


# ── Display-name enrichment ───────────────────────────────────────────────
#
# The conversations payload only stores ``user_id`` per participant. The UI
# (inbox + detail header) needs human-readable names — fetch each
# participant's profile + user once and inline ``display_name`` / ``email``
# so the frontend doesn't N+1 the API.

_DISPLAY_NAME_FIELDS = (
    "farm_name", "company_name", "org_name", "name", "title", "display_name",
    "full_name", "first_name", "business_name",
)


def _pick_display_name(profile_fields: dict | None) -> str:
    if not isinstance(profile_fields, dict):
        return ""
    for key in _DISPLAY_NAME_FIELDS:
        value = profile_fields.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _enrich_participants(conversations: list[dict[str, Any]]) -> None:
    if not conversations:
        return

    from app.modules.auth import repository as auth_repo
    from app.modules.profiles import repository as profile_repo

    user_ids: set[str] = set()
    for conv in conversations:
        for p in conv.get("participants", []) or []:
            uid = p.get("user_id") if isinstance(p, dict) else None
            if uid:
                user_ids.add(str(uid))

    if not user_ids:
        return

    name_by_user: dict[str, str] = {}
    email_by_user: dict[str, str] = {}
    for uid in user_ids:
        user = await auth_repo.find_user_by_id(uid)
        if user:
            email = user.get("email")
            if isinstance(email, str):
                email_by_user[uid] = email
        profile = await profile_repo.get_profile_by_user(uid)
        if profile:
            name_by_user[uid] = _pick_display_name(profile.get("fields"))

    for conv in conversations:
        enriched: list[dict[str, Any]] = []
        for p in conv.get("participants", []) or []:
            if not isinstance(p, dict):
                enriched.append(p)
                continue
            uid = str(p.get("user_id", ""))
            display = name_by_user.get(uid) or email_by_user.get(uid) or ""
            enriched.append({
                **p,
                "display_name": display or None,
                "email": email_by_user.get(uid) or None,
            })
        conv["participants"] = enriched


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
