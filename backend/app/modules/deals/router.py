"""Deal-assembly API — the Story Progression System (GAP-4/5/6).

Two participant primitives drive everything: respond (acknowledge/annotate/correct) and
consent (disclosure advance / audience expansion). The deal is a witnessed story-version
chain; milestones are the only exportable artifacts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.deals import service
from app.modules.deals.schemas import (
    ConsentRequest,
    CreateDealRequest,
    FacilitatorSearchRequest,
    FacilitatorSlotRequest,
    ReopenRequest,
    RespondRequest,
    SetInstrumentRequest,
)

router = APIRouter()


@router.post("")
async def create_deal(
    body: CreateDealRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.create_deal(user, body, config)


@router.get("")
async def list_deals(user: dict = Depends(get_current_user)):
    return await service.list_deals(user)


@router.get("/{deal_id}")
async def get_deal(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_deal(deal_id, user, config)


@router.post("/{deal_id}/respond")
async def respond(
    body: RespondRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    """Acknowledge / annotate / correct the current story version (hash-pinned)."""
    return await service.respond(deal_id, user, body, config)


@router.post("/{deal_id}/advance")
async def advance(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    """Compose the next version from the current milestone + queued annotations."""
    return await service.advance(deal_id, user, config)


@router.post("/{deal_id}/consent")
async def consent(
    body: ConsentRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    """Authorize a disclosure: identity reveal (GAP-6) or audience expansion (GAP-7)."""
    return await service.consent(deal_id, user, body, config)


@router.post("/{deal_id}/instrument")
async def set_instrument(
    body: SetInstrumentRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.set_instrument(deal_id, user, body.instrument, config)


@router.post("/{deal_id}/facilitators")
async def set_facilitator(
    body: FacilitatorSlotRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.set_facilitator(deal_id, user, body, config)


@router.post("/{deal_id}/facilitators/search")
async def search_facilitators(
    body: FacilitatorSearchRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    """Ranked facilitator candidates of a role type, matched to this deal (GAP-7)."""
    return await service.facilitator_candidates(deal_id, user, body.role_type, config)


@router.post("/{deal_id}/reopen")
async def reopen(
    body: ReopenRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.reopen(deal_id, user, body.matter, config)


@router.post("/{deal_id}/versions/{version_id}/revive")
async def revive_version(
    deal_id: str = Path(...),
    version_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.revive_version(deal_id, version_id, user, config)


@router.get("/{deal_id}/brief")
async def get_brief(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.get_brief(deal_id, user, config)


@router.post("/{deal_id}/handoff")
async def handoff(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.handoff(deal_id, user, config)


@router.post("/{deal_id}/cancel")
async def cancel(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.cancel(deal_id, user, config)
