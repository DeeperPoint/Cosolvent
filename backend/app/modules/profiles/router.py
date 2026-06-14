from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request
from app.core.dependencies import get_config, get_current_user, get_optional_user, require_admin
from app.core.exceptions import AppError, ForbiddenError, UnauthorizedError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth.signup_policy import public_application_allowed
from app.modules.discovery import matching as discovery_matching
from app.modules.discovery.schemas import SuggestedMatchesResponse
from app.modules.profiles import service
from app.modules.profiles.register_helpers import ensure_role_matches_route
from app.modules.profiles.register_request import parse_anonymous_register, parse_authenticated_register_body
from app.modules.profiles.schemas import AIProfileActionResponse, DraftUpdateRequest

router = APIRouter()


def _validate_type(type_slug: str, config: MarketplaceConfig) -> str:
    if config.get_type(type_slug) is None:
        from fastapi import HTTPException
        raise HTTPException(404, f"Unknown participant type: {type_slug}")
    return type_slug


@router.post("/{type_slug}/register")
async def register(
    request: Request,
    type_slug: str = Path(...),
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    if user is not None:
        ct = (request.headers.get("content-type") or "").lower()
        if "multipart/form-data" in ct:
            raise AppError("Use application/json when authenticated", status_code=415)
        fields_payload = await parse_authenticated_register_body(request)
        ensure_role_matches_route(user, type_slug)
        return await service.register(user, config, fields_payload)

    email, fields_payload, file_parts = await parse_anonymous_register(request)
    if not email:
        raise UnauthorizedError("email is required when no session is present")
    if not public_application_allowed(config):
        raise ForbiddenError("Public application submission is disabled")
    return await service.submit_application_without_account(
        email,
        type_slug,
        config,
        fields_payload,
        file_parts=file_parts or None,
    )


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


@router.get(
    "/{type_slug}/{profile_id}/suggested-matches",
    response_model=SuggestedMatchesResponse,
)
async def suggested_matches(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    target_type: str | None = Query(None, description="Counterpart participant type to score against. Defaults to the first opposite-role type."),
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum cosine similarity (pre-composite) for a candidate to be considered."),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _validate_type(type_slug, config)
    return await discovery_matching.suggested_matches(
        config,
        profile_id=profile_id,
        type_slug=type_slug,
        viewer=user,
        target_type=target_type,
        limit=limit,
        min_score=min_score,
    )
