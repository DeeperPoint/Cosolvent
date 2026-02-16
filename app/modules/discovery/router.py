"""Discovery / search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_config, get_optional_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.discovery import service
from app.modules.discovery.schemas import SearchRequest

router = APIRouter()


@router.post("")
async def search(
    body: SearchRequest,
    config: MarketplaceConfig = Depends(get_config),
    viewer: dict | None = Depends(get_optional_user),
):
    return await service.search(
        config=config,
        query=body.query,
        filters=body.filters,
        viewer=viewer,
        page=body.page,
        page_size=body.page_size,
    )


@router.post("/{type_slug}")
async def search_type(
    type_slug: str,
    body: SearchRequest,
    config: MarketplaceConfig = Depends(get_config),
    viewer: dict | None = Depends(get_optional_user),
):
    return await service.search(
        config=config,
        query=body.query,
        filters=body.filters,
        participant_type=type_slug,
        viewer=viewer,
        page=body.page,
        page_size=body.page_size,
    )
