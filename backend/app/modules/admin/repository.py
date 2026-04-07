from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from app.core.database import get_collection


# ── Dashboard ────────────────────────────────────────────────────────────

async def get_dashboard_stats() -> dict[str, Any]:
    db = get_collection("users").database
    users_count = await db.users.count_documents({})
    profiles_count = await db.profiles.count_documents({"status": "active"})
    pending_apps = await db.applications.count_documents({"status": "pending"})
    conversations_count = await db.conversations.count_documents({})
    messages_count = await db.messages.count_documents({})

    # Per-type counts
    type_counts: dict[str, int] = {}
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$participant_type", "count": {"$sum": 1}}},
    ]
    aggregate_cursor = await db.profiles.aggregate(pipeline)
    async for doc in aggregate_cursor:
        type_counts[doc["_id"]] = doc["count"]

    return {
        "total_users": users_count,
        "active_profiles": profiles_count,
        "pending_applications": pending_apps,
        "total_conversations": conversations_count,
        "total_messages": messages_count,
        "profiles_by_type": type_counts,
    }


async def list_users(skip: int = 0, limit: int = 50) -> list[dict]:
    cursor = get_collection("users").find(
        {}, {"password_hash": 0}
    ).skip(skip).limit(limit).sort("created_at", -1)
    return await cursor.to_list(length=limit)


# ── User Management ──────────────────────────────────────────────────────

async def get_user(user_id: str) -> dict | None:
    return await get_collection("users").find_one(
        {"_id": user_id}, {"password_hash": 0}
    )


async def update_user_role(user_id: str, role: str) -> dict | None:
    return await get_collection("users").find_one_and_update(
        {"_id": user_id},
        {"$set": {"role": role, "updated_at": datetime.now(timezone.utc)}},
        projection={"password_hash": 0},
        return_document=True,
    )


async def deactivate_user(user_id: str) -> dict | None:
    return await get_collection("users").find_one_and_update(
        {"_id": user_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
        projection={"password_hash": 0},
        return_document=True,
    )


async def activate_user(user_id: str) -> dict | None:
    return await get_collection("users").find_one_and_update(
        {"_id": user_id},
        {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}},
        projection={"password_hash": 0},
        return_document=True,
    )


# ── Conversation Oversight ───────────────────────────────────────────────

async def list_all_conversations(
    skip: int = 0, limit: int = 50, status: str | None = None
) -> list[dict]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    cursor = get_collection("conversations").find(query).skip(skip).limit(limit).sort("created_at", -1)
    return await cursor.to_list(length=limit)


async def get_conversation_messages(
    conversation_id: str, skip: int = 0, limit: int = 50
) -> list[dict]:
    cursor = get_collection("messages").find(
        {"conversation_id": conversation_id}
    ).skip(skip).limit(limit).sort("created_at", 1)
    return await cursor.to_list(length=limit)


# ── FAQ ──────────────────────────────────────────────────────────────────

async def create_faq(data: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        **data,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_collection("faqs").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_faq(faq_id: str) -> dict | None:
    return await get_collection("faqs").find_one({"_id": faq_id})


async def update_faq(faq_id: str, updates: dict) -> dict | None:
    updates["updated_at"] = datetime.now(timezone.utc)
    return await get_collection("faqs").find_one_and_update(
        {"_id": faq_id},
        {"$set": updates},
        return_document=True,
    )


async def delete_faq(faq_id: str) -> bool:
    result = await get_collection("faqs").delete_one({"_id": faq_id})
    return result.deleted_count > 0


async def list_faqs(active_only: bool = False) -> list[dict]:
    query: dict[str, Any] = {}
    if active_only:
        query["is_active"] = True
    cursor = get_collection("faqs").find(query).sort("sort_order", 1)
    return await cursor.to_list(length=500)
