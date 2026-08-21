"""Pre-computed showcase reads — public, unauthenticated, no live vector search or
LLM call. This is the participant-facing half of Phase 6a 'Mode 1'; precompute
itself is admin-triggered (see admin/router.py's /showcase/run)."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query

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
