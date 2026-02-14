from __future__ import annotations

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.files import repository as repo
from app.modules.files import storage


async def upload_file(
    user_id: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    privacy: str = "public",
    category: str = "general",
    profile_id: str | None = None,
) -> dict:
    url = await storage.upload_file(file_bytes, filename, content_type)
    file_doc = await repo.create_file(
        user_id=user_id,
        filename=filename,
        url=url,
        content_type=content_type,
        privacy=privacy,
        category=category,
        profile_id=profile_id,
    )
    return _file_response(file_doc)


async def get_file(file_id: str, user: dict) -> dict:
    file_doc = await repo.get_file(file_id)
    if not file_doc:
        raise NotFoundError("File not found")
    # Private files only visible to owner and admin
    if file_doc["privacy"] == "private":
        if file_doc["user_id"] != str(user["_id"]) and user.get("role") != "admin":
            raise ForbiddenError("Access denied")
    return _file_response(file_doc)


async def delete_file(file_id: str, user: dict) -> None:
    file_doc = await repo.get_file(file_id)
    if not file_doc:
        raise NotFoundError("File not found")
    if file_doc["user_id"] != str(user["_id"]) and user.get("role") != "admin":
        raise ForbiddenError("Not your file")
    await storage.delete_file(file_doc["url"])
    await repo.delete_file(file_id)


async def list_profile_files(profile_id: str) -> list[dict]:
    files = await repo.list_files_for_profile(profile_id)
    return [_file_response(f) for f in files]


async def create_private_asset(
    user_id: str,
    profile_id: str,
    participant_type: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict:
    url = await storage.upload_file(file_bytes, filename, content_type)
    asset = await repo.create_private_asset(
        user_id=user_id,
        profile_id=profile_id,
        participant_type=participant_type,
        filename=filename,
        url=url,
        content_type=content_type,
    )
    return _asset_response(asset)


async def list_private_assets(profile_id: str) -> list[dict]:
    assets = await repo.list_private_assets(profile_id)
    return [_asset_response(a) for a in assets]


async def delete_private_asset(asset_id: str, user: dict) -> None:
    asset = await repo.get_private_asset(asset_id)
    if not asset:
        raise NotFoundError("Asset not found")
    if asset["user_id"] != str(user["_id"]) and user.get("role") != "admin":
        raise ForbiddenError("Not your asset")
    await storage.delete_file(asset["url"])
    await repo.delete_private_asset(asset_id)


def _file_response(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "profile_id": doc.get("profile_id"),
        "filename": doc["filename"],
        "url": doc["url"],
        "content_type": doc["content_type"],
        "privacy": doc.get("privacy", "public"),
        "category": doc.get("category", "general"),
        "created_at": str(doc.get("created_at", "")),
    }


def _asset_response(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "profile_id": doc["profile_id"],
        "participant_type": doc["participant_type"],
        "filename": doc["filename"],
        "url": doc["url"],
        "content_type": doc["content_type"],
        "created_at": str(doc.get("created_at", "")),
    }
