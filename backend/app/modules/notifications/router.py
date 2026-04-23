from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.dependencies import get_current_user
from app.core.response_models import JSONList, JSONObject
from app.modules.notifications import service

router = APIRouter()


@router.get("", response_model=JSONList)
async def list_notifications(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(get_current_user),
):
    return await service.list_notifications(str(user["_id"]), skip, limit)


@router.put("/{notification_id}/read", response_model=JSONObject)
async def mark_read(
    notification_id: str = Path(...),
    _user: dict = Depends(get_current_user),
):
    return await service.mark_read(notification_id)
