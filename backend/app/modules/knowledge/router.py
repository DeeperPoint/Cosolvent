"""Reference-library (Knowledge Slot) domain-Q&A routes.

Public:  grounded, cited Q&A over the curated reference library.
Admin:   curator view of questions the library could not answer (gap signals).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_optional_user, require_admin
from app.modules.knowledge import service
from app.modules.knowledge.schemas import AskRequest, AskResponse, GapSignalList

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    _viewer: dict | None = Depends(get_optional_user),
):
    """Answer a question strictly from the reference library, with citations.

    Unanswerable questions are recorded as knowledge gap signals for curators.
    """
    return await service.ask(
        query=body.query,
        filters=body.filters,
        vertical=body.vertical,
        top_k=body.top_k,
    )


@router.get("/gaps", response_model=GapSignalList)
async def gaps(
    vertical: str | None = None,
    limit: int = 100,
    _admin: dict = Depends(require_admin),
):
    """Curator view: questions the reference library could not answer."""
    return await service.list_gaps(vertical=vertical, limit=limit)
