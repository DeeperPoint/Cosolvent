"""Pydantic models for the Knowledge Slot / Reference Library API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceChunkInput(BaseModel):
    """A single chunk as produced by the KnowledgeSlot pipeline.

    `embedding` is optional: when omitted, the service embeds
    `contextual_content` itself; when present (the normal case for JSONL
    produced upstream), it is stored as-is to avoid re-embedding.
    """

    chunk_id: str
    content: str
    contextual_content: str
    metadata: dict = Field(default_factory=dict)
    embedding: list[float] | None = None


class ReferenceDocumentInput(BaseModel):
    """A reference document plus its chunks, ready to ingest."""

    doc_key: str
    vertical: str = "default"
    title: str | None = None
    source_document: str | None = None
    source_url: str | None = None
    doc_metadata: dict = Field(default_factory=dict)
    chunks: list[ReferenceChunkInput] = Field(default_factory=list)


class IngestRequest(BaseModel):
    documents: list[ReferenceDocumentInput]


class IngestResponse(BaseModel):
    documents_upserted: int
    chunks_upserted: int


class RetrieveRequest(BaseModel):
    query: str
    # Metadata pre-filter applied with JSONB containment (e.g. {"jurisdiction": ["Canada"], "topic": "payment_terms"}).
    filters: dict | None = None
    vertical: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalResult(BaseModel):
    chunk_id: str
    doc_key: str
    title: str | None = None
    source_document: str | None = None
    content: str
    contextual_content: str
    score: float
    metadata: dict = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrievalResult]
