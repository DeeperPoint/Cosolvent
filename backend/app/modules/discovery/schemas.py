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


class SuggestedMatchScoreBreakdown(BaseModel):
    vector: float
    field_overlap: float
    vector_weight: float
    field_overlap_weight: float


class SuggestedMatchResult(BaseModel):
    id: str
    participant_type: str
    score: float
    score_breakdown: SuggestedMatchScoreBreakdown
    fields: dict


class SuggestedMatchesResponse(BaseModel):
    results: list[SuggestedMatchResult]
    total: int
    target_type: str
