"""Generated role alias router.

These aliases provide stable role-specific endpoints while preserving
the generic /api/profiles/{type_slug}/... routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_config, get_current_user, get_optional_user, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.modules.profiles import service
from app.modules.profiles.schemas import AIProfileActionResponse, DraftUpdateRequest

SPEC_HASH = "096ab1bd61cf63b4c1b6209f8d9845f43e0235b00edffc18669afbe7ce089525"
ROLE_SLUGS = ['producer', 'buyer']

router = APIRouter(tags=["generated-roles"])


def _ensure_role_user(user: dict, role_slug: str) -> None:
    if user.get("role") == "admin":
        return
    participant_type = user.get("participant_type")
    if participant_type != role_slug:
        raise HTTPException(
            status_code=403,
            detail=f"Role alias '{role_slug}' does not match your participant type '{participant_type}'",
        )

@router.post("/api/roles/producer/register")
async def register_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.register(user, config)


@router.get("/api/roles/producer/draft")
async def get_draft_producer(
    user: dict = Depends(get_current_user),
):
    _ensure_role_user(user, "producer")
    return await service.get_draft(user)


@router.put("/api/roles/producer/draft")
async def update_draft_producer(
    body: DraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.update_draft(user, body.fields, config)


@router.post("/api/roles/producer/draft/submit")
async def submit_draft_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.submit_draft(user, config)


@router.get("/api/roles/producer/me")
async def me_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.get_my_profile(user, config)


@router.get("/api/roles/producer/{profile_id}")
async def get_profile_producer(
    profile_id: str,
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_profile(profile_id, "producer", config, user)


@router.put("/api/roles/producer/{profile_id}")
async def update_profile_producer(
    profile_id: str,
    body: DraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.update_profile(profile_id, user, body.fields, config)


@router.post("/api/roles/producer/{profile_id}/ai-generate", response_model=AIProfileActionResponse)
async def ai_generate_producer(
    profile_id: str,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.ai_generate_profile(profile_id, user, config)


@router.post("/api/roles/producer/{profile_id}/ai-approve", response_model=AIProfileActionResponse)
async def ai_approve_producer(
    profile_id: str,
    _admin: dict = Depends(require_admin),
):
    return await service.ai_approve_profile(profile_id)


@router.post("/api/roles/producer/{profile_id}/ai-reject", response_model=AIProfileActionResponse)
async def ai_reject_producer(
    profile_id: str,
    _admin: dict = Depends(require_admin),
):
    return await service.ai_reject_profile(profile_id)


@router.post("/api/roles/buyer/register")
async def register_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.register(user, config)


@router.get("/api/roles/buyer/draft")
async def get_draft_buyer(
    user: dict = Depends(get_current_user),
):
    _ensure_role_user(user, "buyer")
    return await service.get_draft(user)


@router.put("/api/roles/buyer/draft")
async def update_draft_buyer(
    body: DraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.update_draft(user, body.fields, config)


@router.post("/api/roles/buyer/draft/submit")
async def submit_draft_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.submit_draft(user, config)


@router.get("/api/roles/buyer/me")
async def me_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.get_my_profile(user, config)


@router.get("/api/roles/buyer/{profile_id}")
async def get_profile_buyer(
    profile_id: str,
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_profile(profile_id, "buyer", config, user)


@router.put("/api/roles/buyer/{profile_id}")
async def update_profile_buyer(
    profile_id: str,
    body: DraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.update_profile(profile_id, user, body.fields, config)


@router.post("/api/roles/buyer/{profile_id}/ai-generate", response_model=AIProfileActionResponse)
async def ai_generate_buyer(
    profile_id: str,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.ai_generate_profile(profile_id, user, config)


@router.post("/api/roles/buyer/{profile_id}/ai-approve", response_model=AIProfileActionResponse)
async def ai_approve_buyer(
    profile_id: str,
    _admin: dict = Depends(require_admin),
):
    return await service.ai_approve_profile(profile_id)


@router.post("/api/roles/buyer/{profile_id}/ai-reject", response_model=AIProfileActionResponse)
async def ai_reject_buyer(
    profile_id: str,
    _admin: dict = Depends(require_admin),
):
    return await service.ai_reject_profile(profile_id)
