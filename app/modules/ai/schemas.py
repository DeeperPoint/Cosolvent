from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    thread_id: str | None = None
    filters: dict | None = None


class FollowUpRequest(BaseModel):
    thread_id: str


class DocumentUpload(BaseModel):
    filename: str
    content: str


class PromptUpdate(BaseModel):
    template: str


class LLMSettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
