"""Pydantic models for reference-library domain Q&A and gap signals."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str
    # Metadata pre-filter applied to reference_metadata (e.g. {"jurisdiction": "Canada"}).
    filters: dict | None = None
    vertical: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)


class Citation(BaseModel):
    # The bracketed key the model cited, e.g. "27_2025".
    key: str
    source_doc_id: str | None = None
    # reference_library row ids backing this citation.
    chunk_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AskResponse(BaseModel):
    query: str
    # False when the reference library does not cover the question (a gap was logged).
    answered: bool
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    # reference_library row ids supplied to the model as context (for transparency).
    used_chunks: list[str] = Field(default_factory=list)


class GapSignal(BaseModel):
    id: str
    query: str
    vertical: str | None = None
    filters: dict = Field(default_factory=dict)
    reason: str
    created_at: str | None = None


class GapSignalList(BaseModel):
    gaps: list[GapSignal]
