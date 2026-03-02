from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Body
import logging
logger = logging.getLogger("cosolvent")

from app.core.dependencies import get_config, get_current_user, get_optional_user, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.modules.profiles import service
from app.modules.profiles.schemas import AIProfileActionResponse, DraftUpdateRequest

router = APIRouter()


def _validate_type(type_slug: str, config: MarketplaceConfig) -> str:
    if config.get_type(type_slug) is None:
        from fastapi import HTTPException
        raise HTTPException(404, f"Unknown participant type: {type_slug}")
    return type_slug


@router.post("/{type_slug}/register")
async def register(
    type_slug: str = Path(...),
    body: DraftUpdateRequest | None = Body(None),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    logger.info(f"DEBUG: router register body: {body}")
    _validate_type(type_slug, config)
    fields = body.fields if body else None
    return await service.register(user, config, fields)


@router.get("/{type_slug}/draft")
async def get_draft(
    type_slug: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.get_draft(user)


@router.put("/{type_slug}/draft")
async def update_draft(
    body: DraftUpdateRequest,
    type_slug: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.update_draft(user, body.fields, config)


@router.post("/{type_slug}/draft/submit")
async def submit_draft(
    type_slug: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.submit_draft(user, config)


@router.get("/{type_slug}/me")
async def get_my_profile(
    type_slug: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.get_my_profile(user, config)


@router.get("/{type_slug}/{profile_id}")
async def get_profile(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.get_profile(profile_id, type_slug, config, user)


@router.put("/{type_slug}/{profile_id}")
async def update_profile(
    body: DraftUpdateRequest,
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.update_profile(profile_id, user, body.fields, config)


@router.post("/{type_slug}/{profile_id}/ai-generate", response_model=AIProfileActionResponse)
async def ai_generate(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await service.ai_generate_profile(profile_id, user, config)


@router.post("/{type_slug}/{profile_id}/ai-approve", response_model=AIProfileActionResponse)
async def ai_approve(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    _admin: dict = Depends(require_admin),
):
    return await service.ai_approve_profile(profile_id)


@router.post("/{type_slug}/{profile_id}/ai-reject", response_model=AIProfileActionResponse)
async def ai_reject(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    _admin: dict = Depends(require_admin),
):
    return await service.ai_reject_profile(profile_id)
