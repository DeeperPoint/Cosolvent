"""Pre-computed showcase reads — public, unauthenticated, no live vector search or
LLM call. This is the participant-facing half of Phase 6a 'Mode 1'; precompute
itself is admin-triggered (see admin/router.py's /showcase/run)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.dependencies import get_config
from app.core.marketplace_config import MarketplaceConfig
from app.modules.showcase import service

router = APIRouter()


@router.get("/personas/{participant_type}")
async def list_personas(participant_type: str = Path(...), limit: int = Query(30, ge=1, le=100)):
    return {"personas": await service.get_personas(participant_type, limit=limit)}


@router.get("/personas/{participant_type}/{profile_id}/matches")
async def persona_matches(participant_type: str = Path(...), profile_id: str = Path(...)):
    return {"matches": await service.get_matches(participant_type, profile_id)}


@router.get("/qa/{participant_type}")
async def persona_qa(participant_type: str = Path(...)):
    return {"qa": await service.get_qa(participant_type)}


@router.get("/runs")
async def list_runs(limit: int = Query(20, ge=1, le=100)):
    """Precompute runs, newest first. Public: it describes the cache, not people."""
    return {"runs": await service.get_runs(limit=limit)}


@router.get("/personas/{participant_type}/{profile_id}/ledger")
async def persona_ledger(
    participant_type: str = Path(...),
    profile_id: str = Path(...),
    limit: int = Query(50, ge=1, le=200),
):
    """Every score this persona's pairings have been given, across runs.

    The cache holds only the latest result; this is what makes a change in a
    score visible rather than silent.
    """
    return {"ledger": await service.get_ledger(participant_type, profile_id, limit=limit)}


@router.get("/market")
async def market_shape(config: MarketplaceConfig = Depends(get_config)):
    """The market's own shape: its name, its participant types and their fields.

    Public, because Mode 1 is anonymous and a visitor cannot render a market it
    cannot describe. Nothing here is private: the field definitions are the
    registration form every prospective participant already sees, and the role
    kinds are what the matcher pairs on.
    """
    types = []
    for pt in config.participant_types:
        schema = config.profile_schemas.get(pt.slug)
        fields = []
        for field in (list(schema.all_fields) if schema else []):
            fields.append({
                "name": field.name,
                "label": getattr(field, "label", None) or field.name,
                "type": field.type,
                "required": bool(getattr(field, "required", False)),
                "options": list(getattr(field, "options", None) or []) or None,
            })
        types.append({
            "slug": pt.slug,
            "label": pt.name,
            "role_kind": pt.role,
            "searchable": pt.slug in (config.discovery.searchable_types or []),
            # What this role may do, so a client can explain a refusal instead of
            # offering an action and then reporting 403. Who may search and who
            # may be found are separate settings: 'searchable' above is the
            # second, can_search here is the first.
            "permissions": pt.permissions.model_dump(),
            "fields": fields,
        })
    return {"marketplace": config.marketplace.name, "participant_types": types}
