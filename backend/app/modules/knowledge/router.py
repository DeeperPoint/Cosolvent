"""Reference library (Knowledge Slot) routes.

Public:  domain retrieval (cited chunks) for Q&A / matching context.
Admin:   ingest, stats, and delete of sponsor-curated reference content.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_optional_user, require_admin
from app.modules.knowledge import service
from app.modules.knowledge.schemas import (
    IngestRequest,
    IngestResponse,
    RetrieveRequest,
    RetrieveResponse,
)

router = APIRouter()


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    _viewer: dict | None = Depends(get_optional_user),
):
    """Return the best-matching reference chunks for a query, with citations."""
    return await service.retrieve(
        query=body.query,
        filters=body.filters,
        vertical=body.vertical,
        top_k=body.top_k,
        min_score=body.min_score,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    _admin: dict = Depends(require_admin),
):
    """Upsert reference documents + chunks (idempotent on doc_key / chunk_id)."""
    return await service.ingest_documents(body.documents)


@router.get("/stats")
async def stats(
    vertical: str | None = None,
    _admin: dict = Depends(require_admin),
):
    return await service.stats(vertical)


@router.delete("/documents/{doc_key}")
async def delete_document(
    doc_key: str,
    _admin: dict = Depends(require_admin),
):
    found = await service.delete_document(doc_key)
    return {"deleted": found, "doc_key": doc_key}
