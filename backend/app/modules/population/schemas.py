"""Pydantic models for population ingest."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PopulationImportRequest(BaseModel):
    """Inline population import. Mode is explicit, never a silent default."""

    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Population records: participant_type, external_id, fields, _watermark",
    )
    mode: Literal["demo", "production"] = Field(
        "demo",
        description="demo requires a valid watermark; production rejects watermarked records",
    )
    index: bool = Field(True, description="Generate embeddings and index into pgvector")


class PopulationImportResult(BaseModel):
    mode: str
    total: int
    loaded: int = 0             # newly created synthetic profiles
    updated: int = 0           # existing external_id upserted in place
    rejected_watermark: int = 0  # failed the GAP-9 watermark gate
    skipped_invalid: int = 0    # failed structural / schema validation
    indexed: int = 0
    errors: list[str] = Field(default_factory=list)
