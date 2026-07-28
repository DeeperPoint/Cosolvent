from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str | None = None
    filters: dict | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    id: str
    participant_type: str
    fields: dict
    score: float | None = None
    ai_profile: str | None = None


class SuggestedMatchSlot(BaseModel):
    score: float
    weight: float


class SuggestedMatchGate(BaseModel):
    name: str
    field: str
    passed: bool
    reason: str | None = None


class SuggestedMatchScoreBreakdown(BaseModel):
    vector: float
    vector_weight: float
    # Legacy field-overlap blend — present when no matching profile is configured.
    field_overlap: float | None = None
    field_overlap_weight: float | None = None
    # Config-driven weighted slots + hard gates (GAP-3) — present when a matching
    # profile is configured for the target type.
    slots: dict[str, SuggestedMatchSlot] | None = None
    gates: list[SuggestedMatchGate] | None = None


class SuggestedMatchResult(BaseModel):
    id: str
    participant_type: str
    score: float
    score_breakdown: SuggestedMatchScoreBreakdown
    fields: dict
    # Set on candidates excluded by a hard gate (returned in the response's `gated`
    # list so the "why gated out" reasons are visible).
    gated: bool | None = None
    gate_failures: list[str] | None = None


class SuggestedMatchesResponse(BaseModel):
    results: list[SuggestedMatchResult]
    total: int
    target_type: str
    # Candidates excluded by hard gates, ranked; only present when a matching
    # profile is configured.
    gated: list[SuggestedMatchResult] | None = None
