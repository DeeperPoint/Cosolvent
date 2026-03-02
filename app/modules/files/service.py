from __future__ import annotations

import logging
from io import BytesIO
from typing import BinaryIO, cast

from app.core.config import settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.permission_engine import check_permission
from app.modules.files import repository as repo
from app.modules.files import storage
from app.modules.files.schemas import FilePrivacy
from app.modules.profiles import repository as profiles_repo

logger = logging.getLogger("cosolvent")


async def upload_file_stream(
    user: dict,
    config: MarketplaceConfig,
    file_obj: BinaryIO,
    filename: str,
    content_type: str,
    size_bytes: int,
    privacy: str = "public",
    category: str = "general",
    profile_id: str | None = None,
) -> dict:
    normalized_privacy = _normalize_requested_privacy(privacy)
    await _ensure_private_upload_allowed(user, config, normalized_privacy)

    user_id = str(user["_id"])
    if not profile_id and user.get("role") != "admin":
        draft = await profiles_repo.get_draft(user_id)
        if draft:
            profile_id = str(draft["_id"])

    await _ensure_profile_attachment_authorized(profile_id, user)

    uploaded = await storage.upload_fileobj(file_obj, filename, content_type)
    try:
        file_doc = await repo.create_file(
            user_id=str(user["_id"]),
            filename=filename,
            s3_key=uploaded.key,
            url=uploaded.url,
            size_bytes=size_bytes,
            content_type=content_type,
            privacy=normalized_privacy,
            category=category,
            profile_id=profile_id,
        )
    except Exception:
        try:
            await storage.delete_file(s3_key=uploaded.key, url=uploaded.url)
        except Exception:
            logger.exception("Failed to rollback uploaded file after metadata write error")
        raise

    response_url = await _resolve_file_url(file_doc, normalized_privacy)
    return _file_response(file_doc, privacy=normalized_privacy, url=response_url)


async def upload_file(
    user: dict,
    config: MarketplaceConfig,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    privacy: str = "public",
    category: str = "general",
    profile_id: str | None = None,
) -> dict:
    return await upload_file_stream(
        user=user,
        config=config,
        file_obj=BytesIO(file_bytes),
        filename=filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
        privacy=privacy,
        category=category,
        profile_id=profile_id,
    )


async def get_file(file_id: str, user: dict) -> dict:
    file_doc = await repo.get_file(file_id)
    if not file_doc:
        raise NotFoundError("File not found")

    normalized_privacy = _normalize_stored_privacy(file_doc.get("privacy"))
    if normalized_privacy == "private":
        if file_doc["user_id"] != str(user["_id"]) and user.get("role") != "admin":
            raise ForbiddenError("Access denied")

    response_url = await _resolve_file_url(file_doc, normalized_privacy)
    return _file_response(file_doc, privacy=normalized_privacy, url=response_url)


async def delete_file(file_id: str, user: dict) -> None:
    file_doc = await repo.get_file(file_id)
    if not file_doc:
        raise NotFoundError("File not found")
    if file_doc["user_id"] != str(user["_id"]) and user.get("role") != "admin":
        raise ForbiddenError("Not your file")

    try:
        await storage.delete_file(s3_key=file_doc.get("s3_key"), url=file_doc.get("url"))
    except Exception:
        logger.exception("S3 delete failed", extra={"file_id": file_id, "user_id": file_doc.get("user_id")})
        raise
    await repo.delete_file(file_id)


async def list_profile_files(profile_id: str) -> list[dict]:
    files = await repo.list_files_for_profile(profile_id)
    return [_file_response(f, privacy=_normalize_stored_privacy(f.get("privacy")), url=f.get("url", "")) for f in files]


async def create_private_asset(
    user_id: str,
    profile_id: str,
    participant_type: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict:
    uploaded = await storage.upload_file(file_bytes, filename, content_type)
    try:
        asset = await repo.create_private_asset(
            user_id=user_id,
            profile_id=profile_id,
            participant_type=participant_type,
            filename=filename,
            s3_key=uploaded.key,
            url=uploaded.url,
            size_bytes=len(file_bytes),
            content_type=content_type,
        )
    except Exception:
        try:
            await storage.delete_file(s3_key=uploaded.key, url=uploaded.url)
        except Exception:
            logger.exception("Failed to rollback uploaded private asset after metadata write error")
        raise
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
    try:
        await storage.delete_file(s3_key=asset.get("s3_key"), url=asset.get("url"))
    except Exception:
        logger.exception("S3 delete failed", extra={"asset_id": asset_id, "user_id": asset.get("user_id")})
        raise
    await repo.delete_private_asset(asset_id)


def _normalize_requested_privacy(raw_privacy: str) -> FilePrivacy:
    normalized = str(raw_privacy or "").strip().lower()
    if normalized in settings.files_allowed_privacy:
        return cast(FilePrivacy, normalized)
    raise AppError("Invalid privacy value", status_code=422)


def _normalize_stored_privacy(raw_privacy: str | None) -> FilePrivacy:
    normalized = str(raw_privacy or "").strip().lower()
    if normalized in settings.files_allowed_privacy:
        return cast(FilePrivacy, normalized)
    logger.warning("Encountered invalid file privacy value; enforcing private visibility")
    return "private"


async def _resolve_file_url(doc: dict, privacy: FilePrivacy) -> str:
    if privacy == "public":
        s3_key = doc.get("s3_key")
        if isinstance(s3_key, str) and storage.is_safe_upload_key(s3_key):
            return storage.public_url_for_key(s3_key)
        return str(doc.get("url", ""))

    key = _resolve_file_key(doc)
    if key is None:
        raise NotFoundError("File storage key not available")
    return await storage.generate_presigned_get_url(key, settings.files_private_url_ttl_seconds)


def _resolve_file_key(doc: dict) -> str | None:
    s3_key = doc.get("s3_key")
    if isinstance(s3_key, str) and storage.is_safe_upload_key(s3_key):
        return s3_key
    if isinstance(s3_key, str) and s3_key:
        logger.warning("Skipping unsafe stored s3_key for file")

    url = str(doc.get("url", ""))
    key = storage.extract_upload_key_from_url(url)
    if key:
        logger.info("Using legacy URL-derived key for file access compatibility")
    return key


async def _ensure_profile_attachment_authorized(profile_id: str | None, user: dict) -> None:
    if not profile_id or user.get("role") == "admin":
        return

    user_id = str(user["_id"])
    draft = await profiles_repo.get_draft(user_id)
    if draft and str(draft.get("_id")) == profile_id:
        return

    profile = await profiles_repo.get_profile_by_id(profile_id)
    if profile and profile.get("user_id") == user_id:
        return

    raise ForbiddenError("Cannot attach file to this profile")


async def _ensure_private_upload_allowed(
    user: dict,
    config: MarketplaceConfig,
    privacy: FilePrivacy,
) -> None:
    if privacy != "private" or user.get("role") == "admin":
        return
    participant_type = str(user.get("participant_type", ""))
    if not check_permission(config, participant_type, "can_share_private_assets"):
        raise ForbiddenError("Missing permission: can_share_private_assets")


def _file_response(doc: dict, *, privacy: FilePrivacy, url: str) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "profile_id": doc.get("profile_id"),
        "filename": doc["filename"],
        "s3_key": doc.get("s3_key"),
        "size_bytes": doc.get("size_bytes"),
        "url": url,
        "content_type": doc["content_type"],
        "privacy": privacy,
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
        "s3_key": doc.get("s3_key"),
        "size_bytes": doc.get("size_bytes"),
        "url": doc["url"],
        "content_type": doc["content_type"],
        "created_at": str(doc.get("created_at", "")),
    }
