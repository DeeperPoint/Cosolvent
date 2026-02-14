from __future__ import annotations

from typing import Any

from app.core.database import get_collection


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
    async for doc in db.profiles.aggregate(pipeline):
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
