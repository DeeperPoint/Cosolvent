"""Reputation lookup — public aggregate, no auth (same posture as a storefront's
review summary: the score is meant to be seen by prospective counterparties before
they commit to a deal)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.reputation import service
from app.modules.reputation.schemas import ReputationSummary

router = APIRouter()


@router.get("/{user_id}", response_model=ReputationSummary)
async def get_reputation(user_id: str):
    return await service.get_reputation(user_id)
