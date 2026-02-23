"""Migrate legacy ai_llm_settings to multi-provider schema."""

from __future__ import annotations

import logging

from app.modules.ai import repository as repo

logger = logging.getLogger("cosolvent.ai.migration")


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

    update = {
        "chat_provider": "openai",
        "chat_model": old_model,
        "temperature": old_temperature,
        "max_tokens": old_max_tokens,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "enabled_providers": ["openai"],
        "use_case_overrides": {
            "rag_query": None,
            "follow_up": None,
            "profile_generation": None,
            "document_extraction": None,
        },
    }

    await repo.upsert_llm_settings(update)
    logger.info("Migrated ai_llm_settings to multi-provider schema")
