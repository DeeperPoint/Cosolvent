"""Discovery / search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_config, get_optional_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.discovery import service
from app.modules.discovery.schemas import SearchRequest

router = APIRouter()


@router.get("/list/{type_slug}")
async def list_type(
    type_slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    config: MarketplaceConfig = Depends(get_config),
    viewer: dict | None = Depends(get_optional_user),
):
    """Public, query-less catalog browse -- gated by the listed type's own
    ``can_list`` permission rather than the viewer's ``can_search``."""
    return await service.list_type(
        config=config, type_slug=type_slug, viewer=viewer, page=page, page_size=page_size,
    )


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
