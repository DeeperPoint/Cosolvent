"""Admin HTTP surface for C0 synthetic population ingest (GAP-10 / GAP-9).

The CLI (`python -m cli load-population`) remains the path the admin manual
documents for a real load. This router exposes the same service so an operator
can exercise and inspect the ingest boundary interactively from `/docs` —
including the rejection behaviour, which is the part worth seeing before
trusting a population in a live market.

Admin-only: importing a population writes profiles and users, and the mode flag
decides whether synthetic data is admissible at all.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.dependencies import get_config, require_admin
from app.core.marketplace_config import MarketplaceConfig
from app.modules.population import repository as repo
from app.modules.population.loader import parse_population_text
from app.modules.population.schemas import PopulationImportRequest, PopulationImportResult
from app.modules.population.service import import_population

router = APIRouter()


@router.get("/count", summary="Count synthetic profiles currently loaded")
async def count_synthetic(user: dict = Depends(require_admin)) -> dict[str, int]:
    return {"synthetic_profiles": await repo.count_synthetic_profiles()}


@router.post(
    "/import",
    response_model=PopulationImportResult,
    summary="Import a population from a JSON body (watermark-enforced)",
)
async def import_population_json(
    payload: PopulationImportRequest,
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
) -> PopulationImportResult:
    """Ingest population records supplied inline.

    `mode="demo"` requires a valid synthetic watermark on every record;
    `mode="production"` rejects any watermarked record — the clean cutover.
    """
    if not payload.records:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No records supplied")

    return await import_population(
        config,
        [r if isinstance(r, dict) else r.model_dump() for r in payload.records],
        mode=payload.mode,
        do_index=payload.index,
    )


@router.post(
    "/import-file",
    response_model=PopulationImportResult,
    summary="Import a population.json file upload (watermark-enforced)",
)
async def import_population_file(
    file: UploadFile = File(..., description="population.json produced by ClientSynth"),
    mode: str = Query("demo", pattern="^(demo|production)$"),
    index: bool = Query(True, description="Generate embeddings and index into pgvector"),
    user: dict = Depends(require_admin),
    config: MarketplaceConfig = Depends(get_config),
) -> PopulationImportResult:
    """Ingest an uploaded population file — the same file the CLI consumes."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be UTF-8 encoded JSON") from exc

    try:
        records = parse_population_text(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid population file: {exc}") from exc

    if not records:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Population file contains no records")

    return await import_population(config, records, mode=mode, do_index=index)  # type: ignore[arg-type]
