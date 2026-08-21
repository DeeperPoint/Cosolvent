"""Pre-computed showcase cache (MarketForge Phase 6a 'Mode 1' — a public, read-only
demo that never runs a live vector search or LLM call per visitor)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShowcasePersona(BaseModel):
    profile_id: str
    participant_type: str
    fields: dict[str, Any]


class ShowcaseMatch(BaseModel):
    candidate_profile_id: str
    candidate_participant_type: str
    fields: dict[str, Any]
    score: float
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class ShowcaseQA(BaseModel):
    participant_type: str
    query: str
    answer: str
    answered: bool
    citations: list[dict[str, Any]] = Field(default_factory=list)


class PrecomputeRunResult(BaseModel):
    generated_at: str
    personas_cached: int
    matches_cached: int
    qa_cached: int
    errors: list[str] = Field(default_factory=list)
