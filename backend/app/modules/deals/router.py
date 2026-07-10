from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.deals import service
from app.modules.deals.schemas import (
    AttachDocumentRequest,
    CreateDealRequest,
    FacilitatorSlotRequest,
    ParameterRequest,
    UpdateDealRequest,
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
async def get_deal(deal_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.get_deal(deal_id, user)


@router.patch("/{deal_id}")
async def update_deal(
    body: UpdateDealRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    return await service.update_context(deal_id, user, body.context)


@router.post("/{deal_id}/parameters")
async def upsert_parameter(
    body: ParameterRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    return await service.upsert_parameter(deal_id, user, body)


@router.post("/{deal_id}/facilitators")
async def set_facilitator(
    body: FacilitatorSlotRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    return await service.set_facilitator(deal_id, user, body)


@router.post("/{deal_id}/documents")
async def attach_document(
    body: AttachDocumentRequest,
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    return await service.attach_document(deal_id, user, body.file_id)


@router.post("/{deal_id}/agree")
async def agree(deal_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.agree(deal_id, user)


@router.post("/{deal_id}/brief")
async def assemble_brief(
    deal_id: str = Path(...),
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.assemble_brief(deal_id, user, config)


@router.get("/{deal_id}/brief")
async def get_brief(deal_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.get_brief(deal_id, user)


@router.post("/{deal_id}/handoff")
async def handoff(deal_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.handoff(deal_id, user)


@router.post("/{deal_id}/cancel")
async def cancel(deal_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.cancel(deal_id, user)
