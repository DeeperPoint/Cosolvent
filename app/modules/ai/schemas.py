from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    thread_id: str | None = None
    filters: dict | None = None
    use_case: str = "faq"


class FollowUpRequest(BaseModel):
    thread_id: str


class DocumentUpload(BaseModel):
    filename: str
    content: str
    content_type: str = "text/plain"


class PromptUpdate(BaseModel):
    template: str


class UseCaseOverride(BaseModel):
    provider: str
    model: str


class UseCaseConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024


class MultimodalConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    enabled: bool = True
    max_tokens: int = 1024


class LLMSettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    chat_provider: str | None = None
    chat_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    enabled_providers: list[str] | None = None
    use_case_overrides: dict[str, UseCaseOverride | None] | None = None
    use_case_configs: dict[str, UseCaseConfig | None] | None = None
    multimodal: MultimodalConfig | None = None


class ProviderValidateRequest(BaseModel):
    provider: str
