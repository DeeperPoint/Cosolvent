"""Generated role alias router.

These aliases provide stable role-specific endpoints while preserving
the generic /api/profiles/{type_slug}/... routes.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_config, get_current_user, get_optional_user, require_admin
from app.generated.enums import AIProfileStatusEnum, BuyerBusinessTypeOption, BuyerCountryOption, BuyerCropsOfInterestOption, DraftStatusEnum, ParticipantTypeEnum, ProducerCertificationsOption, ProducerCountryOption, ProducerPrimaryCropsOption, ProfileStatusEnum
from app.core.marketplace_config import MarketplaceConfig
from app.modules.profiles import service
from app.modules.profiles.schemas import AIProfileActionResponse

SPEC_HASH = "cd0965b201144ad27f7976332380d34a776d5ebbfc68543b9c44f550628ba753"
ROLE_SLUGS = ['producer', 'buyer']

router = APIRouter(tags=["profiles"])


def _ensure_role_user(user: dict, role_slug: str) -> None:
    if user.get("role") == "admin":
        return
    participant_type = user.get("participant_type")
    if participant_type != role_slug:
        raise HTTPException(
            status_code=403,
            detail=f"Role alias '{role_slug}' does not match your participant type '{participant_type}'",
        )


def _payload_fields(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True, mode="json")
    return dict(value)

class ProducerDraftFields(BaseModel):
    farm_name: str
    country: ProducerCountryOption
    region: str | None = None
    primary_crops: list[ProducerPrimaryCropsOption]
    description: str | None = None
    annual_production: float | None = None
    certifications: list[ProducerCertificationsOption] | None = None
    protein_content: str | None = None
    storage_capacity: float | None = None
    financial_notes: str | None = None


class ProducerProfileFields(BaseModel):
    farm_name: str | None = None
    country: ProducerCountryOption | None = None
    region: str | None = None
    primary_crops: list[ProducerPrimaryCropsOption] | None = None
    description: str | None = None
    annual_production: float | None = None
    certifications: list[ProducerCertificationsOption] | None = None
    protein_content: str | None = None
    storage_capacity: float | None = None
    financial_notes: str | None = None


class ProducerDraftUpdateRequest(BaseModel):
    fields: ProducerDraftFields


class ProducerDraftResponse(BaseModel):
    id: str
    user_id: str
    participant_type: ParticipantTypeEnum
    status: DraftStatusEnum
    fields: ProducerProfileFields
    created_at: str | None = None
    updated_at: str | None = None


class ProducerProfileResponse(BaseModel):
    id: str
    user_id: str
    participant_type: ParticipantTypeEnum
    status: ProfileStatusEnum
    fields: ProducerProfileFields
    ai_profile: str | None = None
    ai_profile_draft: str | None = None
    ai_profile_status: AIProfileStatusEnum = AIProfileStatusEnum.NONE
    ai_profile_updated_at: str | None = None
    completeness: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class ProducerSubmitPendingResponse(BaseModel):
    status: Literal["pending_review"]
    application_id: str


class ProducerSubmitActiveResponse(BaseModel):
    status: Literal["active"]
    profile_id: str


ProducerSubmitResponse = ProducerSubmitPendingResponse | ProducerSubmitActiveResponse


class BuyerDraftFields(BaseModel):
    org_name: str
    country: BuyerCountryOption
    business_type: BuyerBusinessTypeOption
    description: str | None = None
    crops_of_interest: list[BuyerCropsOfInterestOption] | None = None
    annual_volume_needed: float | None = None


class BuyerProfileFields(BaseModel):
    org_name: str | None = None
    country: BuyerCountryOption | None = None
    business_type: BuyerBusinessTypeOption | None = None
    description: str | None = None
    crops_of_interest: list[BuyerCropsOfInterestOption] | None = None
    annual_volume_needed: float | None = None


class BuyerDraftUpdateRequest(BaseModel):
    fields: BuyerDraftFields


class BuyerDraftResponse(BaseModel):
    id: str
    user_id: str
    participant_type: ParticipantTypeEnum
    status: DraftStatusEnum
    fields: BuyerProfileFields
    created_at: str | None = None
    updated_at: str | None = None


class BuyerProfileResponse(BaseModel):
    id: str
    user_id: str
    participant_type: ParticipantTypeEnum
    status: ProfileStatusEnum
    fields: BuyerProfileFields
    ai_profile: str | None = None
    ai_profile_draft: str | None = None
    ai_profile_status: AIProfileStatusEnum = AIProfileStatusEnum.NONE
    ai_profile_updated_at: str | None = None
    completeness: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class BuyerSubmitPendingResponse(BaseModel):
    status: Literal["pending_review"]
    application_id: str


class BuyerSubmitActiveResponse(BaseModel):
    status: Literal["active"]
    profile_id: str


BuyerSubmitResponse = BuyerSubmitPendingResponse | BuyerSubmitActiveResponse

@router.post("/api/roles/producer/register", response_model=ProducerDraftResponse)
async def register_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.register(user, config)


@router.get("/api/roles/producer/draft", response_model=ProducerDraftResponse)
async def get_draft_producer(
    user: dict = Depends(get_current_user),
):
    _ensure_role_user(user, "producer")
    return await service.get_draft(user)


@router.put("/api/roles/producer/draft", response_model=ProducerDraftResponse)
async def update_draft_producer(
    body: ProducerDraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.update_draft(user, _payload_fields(body.fields), config)


@router.post("/api/roles/producer/draft/submit", response_model=ProducerSubmitResponse)
async def submit_draft_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.submit_draft(user, config)


@router.get("/api/roles/producer/me", response_model=ProducerProfileResponse)
async def me_producer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.get_my_profile(user, config)


@router.get("/api/roles/producer/{profile_id}", response_model=ProducerProfileResponse)
async def get_profile_producer(
    profile_id: str,
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_profile(profile_id, "producer", config, user)


@router.put("/api/roles/producer/{profile_id}", response_model=ProducerProfileResponse)
async def update_profile_producer(
    profile_id: str,
    body: ProducerDraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "producer")
    return await service.update_profile(profile_id, user, _payload_fields(body.fields), config)


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


@router.post("/api/roles/buyer/register", response_model=BuyerDraftResponse)
async def register_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.register(user, config)


@router.get("/api/roles/buyer/draft", response_model=BuyerDraftResponse)
async def get_draft_buyer(
    user: dict = Depends(get_current_user),
):
    _ensure_role_user(user, "buyer")
    return await service.get_draft(user)


@router.put("/api/roles/buyer/draft", response_model=BuyerDraftResponse)
async def update_draft_buyer(
    body: BuyerDraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.update_draft(user, _payload_fields(body.fields), config)


@router.post("/api/roles/buyer/draft/submit", response_model=BuyerSubmitResponse)
async def submit_draft_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.submit_draft(user, config)


@router.get("/api/roles/buyer/me", response_model=BuyerProfileResponse)
async def me_buyer(
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.get_my_profile(user, config)


@router.get("/api/roles/buyer/{profile_id}", response_model=BuyerProfileResponse)
async def get_profile_buyer(
    profile_id: str,
    user: dict | None = Depends(get_optional_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_profile(profile_id, "buyer", config, user)


@router.put("/api/roles/buyer/{profile_id}", response_model=BuyerProfileResponse)
async def update_profile_buyer(
    profile_id: str,
    body: BuyerDraftUpdateRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    _ensure_role_user(user, "buyer")
    return await service.update_profile(profile_id, user, _payload_fields(body.fields), config)


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
