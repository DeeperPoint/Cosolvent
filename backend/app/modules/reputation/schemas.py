"""Pydantic models for post-handoff bidirectional ratings (roadmap §9.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RateDealRequest(BaseModel):
    ratee_user_id: str
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RatingResponse(BaseModel):
    id: str
    deal_id: str
    rater_user_id: str
    ratee_user_id: str
    score: int
    comment: str | None = None
    created_at: str


class ReputationSummary(BaseModel):
    user_id: str
    rating_count: int
    average_score: float | None = None
    # Comment text only — no rater identity, kept deliberately conservative until a
    # real disclosure policy for reviews is designed (see reputation/service.py).
    recent_comments: list[str] = Field(default_factory=list)
