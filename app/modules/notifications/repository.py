from __future__ import annotations

from datetime import datetime, timezone


from app.core.database import get_collection


async def create_notification(
    user_id: str,
    notification_type: str,
    data: dict,
) -> dict:
    doc = {
        "user_id": user_id,
        "type": notification_type,
        "data": data,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("notifications").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def list_notifications(user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
    cursor = (
        get_collection("notifications")
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def mark_read(notification_id: str) -> dict | None:
    return await get_collection("notifications").find_one_and_update(
        {"_id": notification_id},
        {"$set": {"is_read": True}},
        return_document=True,
    )
