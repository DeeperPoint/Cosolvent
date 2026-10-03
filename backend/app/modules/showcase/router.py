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
