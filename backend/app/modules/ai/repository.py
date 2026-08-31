from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from app.core.database import get_collection


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


async def get_embedding_config() -> dict[str, Any]:
    """Return embedding provider/model/dimensions from settings."""
    s = await get_llm_settings()

    provider = "openai"
    model = "text-embedding-3-small"
    dimensions = 1536

    if s:
        provider = s.get("embedding_provider", provider)
        model = s.get("embedding_model", model)
        dimensions = s.get("embedding_dimensions", dimensions)

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
