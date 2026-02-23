"""Provider registry for multi-provider AI support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderID(str, Enum):
    openai = "openai"
    openrouter = "openrouter"
    gemini = "gemini"


@dataclass(frozen=True)
class ProviderSpec:
    id: ProviderID
    name: str
    base_url: str | None
    supports_embeddings: bool
    default_embedding_model: str | None
    default_embedding_dimensions: int | None
    api_key_env_name: str


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    ProviderID.openai: ProviderSpec(
        id=ProviderID.openai,
        name="OpenAI",
        base_url=None,
        supports_embeddings=True,
        default_embedding_model="text-embedding-3-small",
        default_embedding_dimensions=1536,
        api_key_env_name="openai_api_key",
    ),
    ProviderID.openrouter: ProviderSpec(
        id=ProviderID.openrouter,
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        supports_embeddings=False,
        default_embedding_model=None,
        default_embedding_dimensions=None,
        api_key_env_name="openrouter_api_key",
    ),
    ProviderID.gemini: ProviderSpec(
        id=ProviderID.gemini,
        name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        supports_embeddings=True,
        default_embedding_model="text-embedding-004",
        default_embedding_dimensions=768,
        api_key_env_name="gemini_api_key",
    ),
}
