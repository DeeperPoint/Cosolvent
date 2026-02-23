"""AsyncOpenAI client factory for multi-provider support."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.modules.ai.providers import PROVIDER_REGISTRY


def _get_api_key(provider_id: str) -> str:
    spec = PROVIDER_REGISTRY.get(provider_id)
    if not spec:
        raise ServiceUnavailableError(f"Unknown AI provider: {provider_id}")
    key = getattr(settings, spec.api_key_env_name, "")
    if not key:
        raise ServiceUnavailableError(
            f"AI service unavailable: {spec.name} API key not configured"
        )
    return key


def get_chat_client(provider_id: str) -> AsyncOpenAI:
    """Return an AsyncOpenAI client configured for the given provider."""
    key = _get_api_key(provider_id)
    spec = PROVIDER_REGISTRY[provider_id]
    return AsyncOpenAI(api_key=key, base_url=spec.base_url)


def get_embedding_client(provider_id: str) -> AsyncOpenAI:
    """Return an AsyncOpenAI client for embeddings, validating provider support."""
    spec = PROVIDER_REGISTRY.get(provider_id)
    if not spec:
        raise ServiceUnavailableError(f"Unknown AI provider: {provider_id}")
    if not spec.supports_embeddings:
        raise ServiceUnavailableError(
            f"{spec.name} does not support embeddings"
        )
    key = _get_api_key(provider_id)
    return AsyncOpenAI(api_key=key, base_url=spec.base_url)
