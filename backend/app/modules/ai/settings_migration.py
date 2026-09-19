"""Migrate legacy ai_llm_settings to multi-provider schema."""

from __future__ import annotations

import logging

from app.modules.ai import repository as repo

logger = logging.getLogger("cosolvent.ai.migration")

_EMBEDDING_KEYS = ("embedding_provider", "embedding_model", "embedding_dimensions")


async def migrate_llm_settings() -> None:
    """If chat_provider field is missing, migrate old flat settings to new schema."""
    settings = await repo.get_llm_settings()
    if settings is None:
        # No settings stored yet; nothing to migrate.
        return

    if settings.get("chat_provider"):
        # Already migrated.
        return

    old_model = settings.get("model", "gpt-4o-mini")
    old_temperature = settings.get("temperature", 0.7)
    old_max_tokens = settings.get("max_tokens", 1024)

    # Chat defaults to OpenRouter (OpenAI-compatible API). Embeddings follow whichever
    # provider has a key: OpenRouter proxies OpenAI embeddings at the same 1536
    # dimensions, so an OpenRouter-only deployment must not be pointed at OpenAI.
    _chat_model = old_model if "/" in old_model else f"openai/{old_model}"
    embedding_provider, embedding_model, embedding_dimensions = repo.default_embedding_provider()

    update = {
        "chat_provider": "openrouter",
        "chat_model": _chat_model,
        "temperature": old_temperature,
        "max_tokens": old_max_tokens,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "enabled_providers": ["openrouter", "openai"],
        "use_case_overrides": {
            "rag_query": None,
            "follow_up": None,
            "profile_generation": None,
            "document_extraction": None,
        },
    }

    # Fill in what the old schema lacked; never overwrite a choice already stored.
    # An operator who set only the embedding fields (the admin API saves just the
    # fields it is sent) would otherwise have them reset on the next restart, and
    # the next provisioning run would fail preflight for a missing OpenAI key.
    preserved = [key for key in _EMBEDDING_KEYS if settings.get(key) is not None]
    for key in preserved:
        update.pop(key, None)

    await repo.upsert_llm_settings(update)
    if preserved:
        logger.info(
            "Migrated ai_llm_settings to multi-provider schema (kept existing %s)",
            ", ".join(preserved),
        )
    else:
        logger.info("Migrated ai_llm_settings to multi-provider schema")
