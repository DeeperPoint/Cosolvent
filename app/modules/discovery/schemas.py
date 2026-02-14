from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str | None = None
    filters: dict | None = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    id: str
    participant_type: str
    fields: dict
    score: float | None = None
    ai_profile: str | None = None
