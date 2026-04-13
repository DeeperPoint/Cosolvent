from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection


async def create_file(
    filename: str,
    s3_key: str,
    url: str,
    size_bytes: int,
    content_type: str,
    *,
    user_id: str | None = None,
    application_id: str | None = None,
    privacy: str = "public",
    category: str = "general",
    profile_id: str | None = None,
) -> dict:
    if user_id is None and application_id is None:
        raise ValueError("create_file requires user_id and/or application_id")
    doc: dict[str, Any] = {
        "filename": filename,
        "s3_key": s3_key,
        "url": url,
        "size_bytes": size_bytes,
        "content_type": content_type,
        "privacy": privacy,
        "category": category,
        "created_at": datetime.now(timezone.utc),
    }
    if user_id is not None:
        doc["user_id"] = user_id
    if application_id is not None:
        doc["application_id"] = application_id
    if profile_id is not None:
        doc["profile_id"] = profile_id
    result = await get_collection("files").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_file(file_id: str) -> dict | None:
    return await get_collection("files").find_one({"_id": file_id})


async def delete_file(file_id: str) -> None:
    await get_collection("files").delete_one({"_id": file_id})


async def list_files_for_profile(profile_id: str) -> list[dict]:
    cursor = get_collection("files").find({"profile_id": profile_id})
    return await cursor.to_list(length=100)


async def count_files_for_profile_owner(user_id: str, profile_id: str) -> int:
    return await get_collection("files").count_documents(
        {"user_id": user_id, "profile_id": profile_id}
    )


async def count_files_for_application(application_id: str) -> int:
    return await get_collection("files").count_documents({"application_id": application_id})


async def list_files_for_application(application_id: str) -> list[dict]:
    cursor = get_collection("files").find({"application_id": application_id})
    return await cursor.to_list(length=200)


async def reassign_application_files_to_profile(
    application_id: str,
    user_id: str,
    profile_id: str,
) -> int:
    """Attach pending-application uploads to the new user profile after approval."""
    col = get_collection("files")
    cursor = col.find({"application_id": application_id})
    docs = await cursor.to_list(length=200)
    count = 0
    for doc in docs:
        await col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "user_id": user_id,
                    "profile_id": profile_id,
                    "application_id": None,
                }
            },
        )
        count += 1
    return count


# ── Private assets ────────────────────────────────────────────────────────

async def create_private_asset(
    user_id: str,
    profile_id: str,
    participant_type: str,
    filename: str,
    s3_key: str,
    url: str,
    size_bytes: int,
    content_type: str,
) -> dict:
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "participant_type": participant_type,
        "filename": filename,
        "s3_key": s3_key,
        "url": url,
        "size_bytes": size_bytes,
        "content_type": content_type,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("private_assets").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_private_asset(asset_id: str) -> dict | None:
    return await get_collection("private_assets").find_one({"_id": asset_id})


async def delete_private_asset(asset_id: str) -> None:
    await get_collection("private_assets").delete_one({"_id": asset_id})


async def list_private_assets(profile_id: str) -> list[dict]:
    cursor = get_collection("private_assets").find({"profile_id": profile_id})
    return await cursor.to_list(length=100)
