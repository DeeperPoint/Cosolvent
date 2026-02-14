from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import get_collection


async def create_file(
    user_id: str,
    filename: str,
    url: str,
    content_type: str,
    privacy: str = "public",
    category: str = "general",
    profile_id: str | None = None,
) -> dict:
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "filename": filename,
        "url": url,
        "content_type": content_type,
        "privacy": privacy,
        "category": category,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("files").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_file(file_id: str) -> dict | None:
    return await get_collection("files").find_one({"_id": ObjectId(file_id)})


async def delete_file(file_id: str) -> None:
    await get_collection("files").delete_one({"_id": ObjectId(file_id)})


async def list_files_for_profile(profile_id: str) -> list[dict]:
    cursor = get_collection("files").find({"profile_id": profile_id})
    return await cursor.to_list(length=100)


# ── Private assets ────────────────────────────────────────────────────────

async def create_private_asset(
    user_id: str,
    profile_id: str,
    participant_type: str,
    filename: str,
    url: str,
    content_type: str,
) -> dict:
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "participant_type": participant_type,
        "filename": filename,
        "url": url,
        "content_type": content_type,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("private_assets").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_private_asset(asset_id: str) -> dict | None:
    return await get_collection("private_assets").find_one({"_id": ObjectId(asset_id)})


async def delete_private_asset(asset_id: str) -> None:
    await get_collection("private_assets").delete_one({"_id": ObjectId(asset_id)})


async def list_private_assets(profile_id: str) -> list[dict]:
    cursor = get_collection("private_assets").find({"profile_id": profile_id})
    return await cursor.to_list(length=100)
