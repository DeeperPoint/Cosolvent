"""Pydantic models for population ingest."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PopulationImportResult(BaseModel):
    mode: str
    total: int
    loaded: int = 0             # newly created synthetic profiles
    updated: int = 0           # existing external_id upserted in place
    rejected_watermark: int = 0  # failed the GAP-9 watermark gate
    skipped_invalid: int = 0    # failed structural / schema validation
    indexed: int = 0
    errors: list[str] = Field(default_factory=list)
