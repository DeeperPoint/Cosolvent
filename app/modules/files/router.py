from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile

from app.core.dependencies import get_current_user
from app.modules.files import service

router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    privacy: str = Form("public"),
    category: str = Form("general"),
    profile_id: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    content = await file.read()
    return await service.upload_file(
        user_id=str(user["_id"]),
        file_bytes=content,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        privacy=privacy,
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
