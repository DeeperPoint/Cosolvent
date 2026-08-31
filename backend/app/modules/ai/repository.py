from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection

logger = logging.getLogger("cosolvent.ai")


# ── AI Documents ──────────────────────────────────────────────────────────

async def create_document(filename: str, content: str, content_type: str = "text/plain") -> dict[str, Any]:
    doc = {
        "filename": filename,
        "content": content,
        "content_type": content_type,
        "status": "QUEUED",
        "chunk_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("ai_documents").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_document(doc_id: str) -> dict[str, Any] | None:
    return await get_collection("ai_documents").find_one({"_id": doc_id})


async def update_document_status(doc_id: str, status: str, chunk_count: int = 0) -> None:
    update: dict[str, Any] = {"status": status}
    if chunk_count:
        update["chunk_count"] = chunk_count
    await get_collection("ai_documents").update_one(
        {"_id": doc_id}, {"$set": update}
    )


async def list_documents(skip: int = 0, limit: int = 50) -> list[dict]:
    cursor = get_collection("ai_documents").find().skip(skip).limit(limit).sort("created_at", -1)
    return await cursor.to_list(length=limit)


async def delete_document(doc_id: str) -> None:
    await get_collection("ai_documents").delete_one({"_id": doc_id})


# ── Prompts ───────────────────────────────────────────────────────────────

async def get_prompt(intent: str) -> dict[str, Any] | None:
    return await get_collection("ai_prompts").find_one({"intent": intent})


async def upsert_prompt(intent: str, template: str) -> dict[str, Any]:
    result = await get_collection("ai_prompts").find_one_and_update(
        {"intent": intent},
        {"$set": {"template": template, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
        return_document=True,
    )
    return result


async def list_prompts() -> list[dict]:
    cursor = get_collection("ai_prompts").find()
    return await cursor.to_list(length=100)


# ── LLM Settings ─────────────────────────────────────────────────────────

async def get_llm_settings() -> dict[str, Any] | None:
    return await get_collection("ai_llm_settings").find_one({"_id": "default"})


async def upsert_llm_settings(settings: dict) -> dict[str, Any]:
    settings_doc = {k: v for k, v in settings.items() if v is not None}
    result = await get_collection("ai_llm_settings").find_one_and_update(
        {"_id": "default"},
        {"$set": settings_doc},
        upsert=True,
        return_document=True,
    )
    return result


# Per-use-case defaults, applied over the global default but under any explicit
# operator override in `ai_llm_settings`. Field extraction (`document_extraction`)
# depends on strict JSON-schema structured output and runs on the anonymous
# registration path, so it defaults to a cheap, schema-reliable model rather than
# whatever the global chat default happens to be.
_USE_CASE_DEFAULTS: dict[str, dict[str, str]] = {
    "document_extraction": {"provider": "openrouter", "model": "google/gemini-2.5-flash"},
}


async def get_resolved_chat_config(use_case: str | None = None) -> dict[str, Any]:
    """Resolve chat config for a given use case, falling back to global defaults."""
    s = await get_llm_settings()

    provider = "openrouter"
    model = "openai/gpt-4o-mini"
    temperature = 0.7
    max_tokens = 1024

    if s:
        provider = s.get("chat_provider", s.get("provider", provider))
        model = s.get("chat_model", s.get("model", model))
        temperature = s.get("temperature", temperature)
        max_tokens = s.get("max_tokens", max_tokens)

    # The use-case default sits between the global default and an explicit
    # override: an operator who set a global chat model did not thereby choose it
    # for extraction, but an explicit per-use-case config below still wins.
    uc_default = _USE_CASE_DEFAULTS.get(use_case or "")
    if uc_default:
        provider = uc_default.get("provider", provider)
        model = uc_default.get("model", model)

    if s:
        # Apply per-use-case config (new-style) first
        if use_case:
            configs = s.get("use_case_configs", {})
            cfg = configs.get(use_case)
            if cfg and isinstance(cfg, dict):
                provider = cfg.get("provider", provider)
                model = cfg.get("model", model)
                temperature = cfg.get("temperature", temperature)
                max_tokens = cfg.get("max_tokens", max_tokens)
            else:
                # Fall back to legacy use_case_overrides (provider/model only)
                overrides = s.get("use_case_overrides", {})
                override = overrides.get(use_case)
                if override and isinstance(override, dict):
                    provider = override.get("provider", provider)
                    model = override.get("model", model)

    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


async def get_multimodal_config() -> dict[str, Any]:
    """Return multimodal extraction config from settings."""
    s = await get_llm_settings()
    defaults: dict[str, Any] = {
        "provider": "openrouter",
        "model": "openai/gpt-4o",
        "enabled": True,
        "max_tokens": 1024,
    }
    if s and "multimodal" in s:
        mm = s["multimodal"]
        if isinstance(mm, dict):
            defaults.update({k: v for k, v in mm.items() if v is not None})
    return defaults


# The pgvector columns storing profile and document embeddings are fixed at this
# width, so a provider whose vectors differ cannot be used without a migration
# and a full re-index.
REQUIRED_EMBEDDING_DIMENSIONS = 1536


def _default_embedding_provider() -> str:
    """Pick a *dimension-compatible* embedding provider that is actually keyed.

    Two failure modes this avoids, both of which surface only at index time —
    after a population has already "loaded" — rather than at startup:

      - Defaulting unconditionally to OpenAI on an instance keyed for a
        different provider: every `index_profile` call raises, and the records
        are present but undiscoverable.
      - Selecting whichever provider happens to hold a key: Gemini's embeddings
        are 768-dimensional and would be rejected by a `Vector(1536)` column on
        every insert.

    Candidates are therefore filtered to providers whose default width matches
    the column, in registry order so behaviour is stable rather than dependent
    on which keys happen to be present. An explicit `embedding_provider`
    setting always wins over this, including a deliberate non-1536 choice paired
    with a migration.
    """
    from app.core.config import settings as app_settings
    from app.modules.ai.providers import PROVIDER_REGISTRY

    for provider_id, spec in PROVIDER_REGISTRY.items():
        if not spec.supports_embeddings:
            continue
        if spec.default_embedding_dimensions != REQUIRED_EMBEDDING_DIMENSIONS:
            continue
        if getattr(app_settings, spec.api_key_env_name, ""):
            name = str(getattr(provider_id, "value", provider_id))
            logger.info("Embedding provider resolved to '%s' (keyed, %d-dim)", name, REQUIRED_EMBEDDING_DIMENSIONS)
            return name

    # Nothing compatible is keyed. Return the conventional default so the failure
    # surfaces as a missing-key error naming a provider, not an empty string.
    return "openai"


async def get_embedding_config() -> dict[str, Any]:
    """Return embedding provider/model/dimensions from settings."""
    s = await get_llm_settings()

    provider = _default_embedding_provider()
    model = None
    dimensions = None

    if s:
        provider = s.get("embedding_provider") or provider
        model = s.get("embedding_model")
        dimensions = s.get("embedding_dimensions")

    if not model or not dimensions:
        # Fall back to the chosen provider's own defaults rather than OpenAI's,
        # so a non-OpenAI provider is not handed an OpenAI model name.
        from app.modules.ai.providers import PROVIDER_REGISTRY

        spec = next(
            (sp for pid, sp in PROVIDER_REGISTRY.items()
             if str(getattr(pid, "value", pid)) == provider),
            None,
        )
        model = model or (spec.default_embedding_model if spec else "text-embedding-3-small")
        dimensions = dimensions or (spec.default_embedding_dimensions if spec else 1536)

    return {
        "provider": provider,
        "model": model,
        "dimensions": dimensions,
    }


# ── Chat History ──────────────────────────────────────────────────────────

async def get_chat_thread(thread_id: str) -> dict[str, Any] | None:
    return await get_collection("ai_chat_history").find_one({"thread_id": thread_id})


async def upsert_chat_thread(
    thread_id: str, user_id: str, messages: list[dict]
) -> dict[str, Any]:
    return await get_collection("ai_chat_history").find_one_and_update(
        {"thread_id": thread_id},
        {
            "$set": {"messages": messages, "updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {"user_id": user_id, "created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
        return_document=True,
    )
