from __future__ import annotations

import asyncio
from typing import BinaryIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile

from app.core.config import settings
from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.files import service

router = APIRouter()


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    privacy: str = Form("public"),
    category: str = Form("general"),
    profile_id: str | None = Form(None),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.files_max_upload_bytes:
                raise HTTPException(413, "File exceeds upload size limit")
        except ValueError:
            pass

    normalized_privacy = _normalize_privacy(privacy)
    try:
        file_size = await _compute_file_size(file.file)
    except ValueError as exc:
        raise HTTPException(400, "Unable to determine file size") from exc
    if file_size > settings.files_max_upload_bytes:
        raise HTTPException(413, "File exceeds upload size limit")

    return await service.upload_file_stream(
        user=user,
        config=config,
        file_obj=file.file,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=file_size,
        privacy=normalized_privacy,
        category=category,
        profile_id=profile_id,
    )


@router.get("/{file_id}")
async def get_file(file_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.get_file(file_id, user)


@router.delete("/{file_id}")
async def delete_file(file_id: str = Path(...), user: dict = Depends(get_current_user)):
    await service.delete_file(file_id, user)
    return {"detail": "Deleted"}


def _normalize_privacy(raw_privacy: str) -> str:
    normalized = str(raw_privacy or "").strip().lower()
    if normalized not in settings.files_allowed_privacy:
        raise HTTPException(422, "Invalid privacy value")
    return normalized


def _compute_size_sync(file_obj: BinaryIO) -> int:
    try:
        current = file_obj.tell()
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(current)
        return size
    except (AttributeError, OSError, ValueError) as exc:
        raise ValueError("size unavailable") from exc


async def _compute_file_size(file_obj: BinaryIO) -> int:
    return await asyncio.to_thread(_compute_size_sync, file_obj)
