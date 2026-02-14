"""Admin routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_config, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.modules.admin import service
from app.modules.admin.schemas import ApprovalAction

router = APIRouter()


@router.get("/dashboard")
async def dashboard(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_dashboard(config)


@router.get("/users")
async def list_users(
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(require_admin),
):
    return await service.list_users(skip, limit)


@router.get("/applications")
async def list_applications(
    status: str | None = Query(None),
    user: dict = Depends(require_admin),
):
    return await service.list_applications(status)


@router.post("/applications/{app_id}/approve")
async def approve_application(
    app_id: str,
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.approve_application(app_id, config)


@router.post("/applications/{app_id}/reject")
async def reject_application(
    app_id: str,
    body: ApprovalAction = ApprovalAction(),
    user: dict = Depends(require_admin),
):
    return await service.reject_application(app_id, body.feedback)


@router.get("/config")
async def get_config_summary(
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_config_summary(config)
