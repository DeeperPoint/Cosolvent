from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import get_collection


# ── Conversations ─────────────────────────────────────────────────────────

async def create_conversation(
    participants: list[dict],
    initiator_id: str,
    rule_key: str,
    status: str = "pending",
) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "participants": participants,
        "initiator_id": initiator_id,
        "rule_key": rule_key,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_collection("conversations").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_conversation(conv_id: str) -> dict | None:
    return await get_collection("conversations").find_one({"_id": ObjectId(conv_id)})


async def update_conversation(conv_id: str, updates: dict) -> dict | None:
    updates["updated_at"] = datetime.now(timezone.utc)
    return await get_collection("conversations").find_one_and_update(
        {"_id": ObjectId(conv_id)},
        {"$set": updates},
        return_document=True,
    )


async def update_conversation_status(conv_id: str, status: str) -> dict | None:
    return await update_conversation(conv_id, {"status": status})


async def list_conversations_for_user(user_id: str) -> list[dict]:
    cursor = get_collection("conversations").find(
        {"participants.user_id": user_id}
    ).sort("updated_at", -1)
    return await cursor.to_list(length=100)


async def find_existing_conversation(user_id_a: str, user_id_b: str) -> dict | None:
    return await get_collection("conversations").find_one({
        "$and": [
            {"participants.user_id": user_id_a},
            {"participants.user_id": user_id_b},
        ],
        "status": {"$ne": "closed"},
    })


# ── Messages ──────────────────────────────────────────────────────────────

async def create_message(
    conversation_id: str,
    sender_id: str,
    content: str,
    content_type: str = "text",
) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "conversation_id": conversation_id,
        "sender_id": sender_id,
        "content": content,
        "content_type": content_type,
        "edited": False,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_collection("messages").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_message(msg_id: str) -> dict | None:
    return await get_collection("messages").find_one({"_id": ObjectId(msg_id)})


async def update_message(msg_id: str, content: str) -> dict | None:
    return await get_collection("messages").find_one_and_update(
        {"_id": ObjectId(msg_id)},
        {"$set": {"content": content, "edited": True, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )


async def delete_message(msg_id: str) -> None:
    await get_collection("messages").delete_one({"_id": ObjectId(msg_id)})


async def list_messages(
    conversation_id: str,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    cursor = (
        get_collection("messages")
        .find({"conversation_id": conversation_id})
        .sort("created_at", 1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
