"""AI service: RAG query pipeline, follow-ups, document management."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import delete

from app.core.database import session_scope
from app.core.db_schema import ai_document_chunks
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.queue import enqueue_job
from app.core.marketplace_config import MarketplaceConfig
from app.modules.ai import repository as repo
from app.modules.ai.embedding_client import get_embedding
from app.modules.ai.llm_client import generate
from app.modules.ai.prompt_manager import format_prompt, get_prompt_template
from app.modules.discovery.vector_service import search_vectors
from app.modules.knowledge import search_reference_library

logger = logging.getLogger("cosolvent.ai.service")


async def query(
    user_id: str,
    query_text: str,
    thread_id: str | None,
    filters: dict | None,
    config: MarketplaceConfig,
    use_case: str = "faq",
) -> dict[str, Any]:
    """RAG query: retrieve relevant context, generate answer."""
    if not config.discovery.ai.rag_query_enabled:
        raise AppError("RAG query is disabled for this marketplace", 400)

    if not thread_id:
        thread_id = str(uuid.uuid4())

    # Retrieve context from vector store
    context = ""
    try:
        embedding = await get_embedding(query_text)
        vector_filter = {"source": "document"}
        if filters:
            vector_filter.update(filters)
        results = await search_vectors(embedding, top_k=5, filter_dict=vector_filter)
        context_parts = [r.get("metadata", {}).get("text", "") for r in results]
        context = "\n\n".join(p for p in context_parts if p)
    except Exception as exc:
        raise ServiceUnavailableError("AI retrieval unavailable: vector search failed") from exc

    # Blend in the sponsor-curated reference library (Knowledge Slot), if any is loaded.
    # Non-fatal: an empty or unavailable library must not break the main answer.
    try:
        ref_hits = await search_reference_library(embedding, top_k=5)
        if ref_hits:
            ref_block = "\n\n".join(h["chunk_text"] for h in ref_hits)
            context = (context + "\n\n" if context else "") + "Curated reference library:\n" + ref_block
    except Exception:
        logger.warning("Reference library retrieval failed; continuing without it", exc_info=True)

    # Build prompt — try use_case template first, fall back to rag_query
    template = await get_prompt_template(use_case, config)
    if not template:
        template = await get_prompt_template("rag_query", config)
    prompt = format_prompt(template, config, context=context, query=query_text)

    # Get conversation history
    thread = await repo.get_chat_thread(thread_id)
    messages = []
    if thread and thread.get("messages"):
        messages = thread["messages"]
    messages.append({"role": "user", "content": prompt})

    # Generate using per-use-case config
    answer = await generate(messages, use_case=use_case)

    # Save to history
    messages.append({"role": "assistant", "content": answer})
    await repo.upsert_chat_thread(thread_id, user_id, messages)

    return {
        "answer": answer,
        "thread_id": thread_id,
    }


async def knowledge_query(
    query_text: str,
    config: MarketplaceConfig,
    *,
    vertical: str | None = None,
    filters: dict | None = None,
    top_k: int = 5,
    use_case: str = "rag_query",
) -> dict[str, Any]:
    """Reference-library-only RAG (the Knowledge Slot Q&A path).

    Unlike ``query``, this is scoped entirely to the curated reference library and
    returns citations. Intended for a dedicated 'Knowledge Q&A' / Demo-Mode endpoint.
    """
    embedding = await get_embedding(query_text)
    hits = await search_reference_library(embedding, top_k=top_k, vertical=vertical, filters=filters)
    context = "\n\n".join(h["chunk_text"] for h in hits)

    template = await get_prompt_template("rag_query", config)
    prompt = format_prompt(template, config, context=context, query=query_text)
    answer = await generate([{"role": "user", "content": prompt}], use_case=use_case)

    return {
        "answer": answer,
        "sources": [{"id": h["id"], "score": h["score"], "metadata": h["metadata"]} for h in hits],
    }


async def follow_up(
    thread_id: str,
    config: MarketplaceConfig,
) -> dict[str, Any]:
    """Generate follow-up question suggestions."""
    if not config.discovery.ai.follow_up_suggestions:
        raise AppError("Follow-up suggestions are disabled for this marketplace", 400)

    thread = await repo.get_chat_thread(thread_id)
    if not thread:
        return {"suggestions": []}

    template = await get_prompt_template("follow_up", config)
    prompt = format_prompt(template, config)

    messages = thread.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    raw = await generate(messages, use_case="follow_up")
    try:
        suggestions = json.loads(raw)
    except json.JSONDecodeError:
        suggestions = [raw]

    return {"suggestions": suggestions, "thread_id": thread_id}


async def upload_document(filename: str, content: str, content_type: str = "text/plain") -> dict[str, Any]:
    doc = await repo.create_document(filename, content, content_type)
    doc_id = str(doc["_id"])
    try:
        await enqueue_job(
            "app.workers.document_indexing.process_document_task",
            doc_id,
            required=True,
        )
    except ServiceUnavailableError:
        await repo.update_document_status(doc_id, "FAILED")
        raise
    return _serialize(doc)


async def list_documents(skip: int = 0, limit: int = 50) -> list[dict]:
    docs = await repo.list_documents(skip, limit)
    return [_serialize(d) for d in docs]


async def delete_document(doc_id: str) -> None:
    # Delete vectors from Postgres vector table.
    try:
        async with session_scope() as session:
            await session.execute(delete(ai_document_chunks).where(ai_document_chunks.c.document_id == uuid.UUID(doc_id)))
            await session.commit()
    except Exception:
        pass
    # Also purge the document's chunks from the reference library ("LLM wiki").
    try:
        from app.core.db_schema import reference_library
        from app.modules.knowledge.service import coerce_doc_id

        async with session_scope() as session:
            await session.execute(
                delete(reference_library).where(reference_library.c.source_doc_id == coerce_doc_id(doc_id))
            )
            await session.commit()
    except Exception:
        pass
    await repo.delete_document(doc_id)


async def get_models(provider: str | None = None) -> list[dict]:
    """Fetch available models, optionally filtered by provider."""
    from app.modules.ai.model_fetcher import fetch_models

    if provider:
        return await fetch_models(provider)

    # Fetch from all enabled providers
    settings = await repo.get_llm_settings()
    enabled = ["openrouter", "openai"]
    if settings:
        enabled = settings.get("enabled_providers", enabled)

    all_models = []
    for p in enabled:
        try:
            models = await fetch_models(p)
            all_models.extend(models)
        except Exception:
            logger.warning("Failed to fetch models for provider %s", p)
    return all_models


async def get_providers() -> list[dict]:
    """Return all providers with their status."""
    from app.core.config import settings as app_settings
    from app.modules.ai.providers import PROVIDER_REGISTRY

    llm_settings = await repo.get_llm_settings()
    enabled = []
    if llm_settings:
        enabled = llm_settings.get("enabled_providers", [])

    result = []
    for pid, spec in PROVIDER_REGISTRY.items():
        key = getattr(app_settings, spec.api_key_env_name, "")
        result.append({
            "id": str(spec.id.value),
            "name": spec.name,
            "enabled": str(spec.id.value) in enabled,
            "configured": bool(key),
            "supports_embeddings": spec.supports_embeddings,
        })
    return result


async def validate_provider(provider_id: str) -> dict:
    """Test if a provider API key is valid."""
    from app.modules.ai.model_fetcher import validate_provider_key
    valid = await validate_provider_key(provider_id)
    return {"provider": provider_id, "valid": valid}


async def get_llm_settings() -> dict:
    settings = await repo.get_llm_settings()
    if not settings:
        return {
            "chat_provider": "openrouter",
            "chat_model": "openai/gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1024,
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
            "enabled_providers": ["openrouter", "openai"],
            "use_case_overrides": {},
            "use_case_configs": {
                "faq":                {"provider": "openrouter", "model": "openai/gpt-4o-mini", "temperature": 0.7,  "max_tokens": 1024},
                "profile_chat":       {"provider": "openrouter", "model": "openai/gpt-4o-mini", "temperature": 0.7,  "max_tokens": 2048},
                "discovery":          {"provider": "openrouter", "model": "openai/gpt-4o-mini", "temperature": 0.3,  "max_tokens": 512},
                "profile_generation": {"provider": "openrouter", "model": "openai/gpt-4o",      "temperature": 0.5,  "max_tokens": 2048},
                "document_extraction":{"provider": "openrouter", "model": "openai/gpt-4o-mini", "temperature": 0.1,  "max_tokens": 1024},
                "follow_up":          {"provider": "openrouter", "model": "openai/gpt-4o-mini", "temperature": 0.7,  "max_tokens": 512},
            },
            "multimodal": {
                "provider": "openrouter",
                "model": "openai/gpt-4o",
                "enabled": True,
                "max_tokens": 1024,
            },
        }
    return _serialize(settings)


async def update_llm_settings(updates: dict) -> dict:
    # Detect embedding dimension changes to trigger migration
    if "embedding_dimensions" in updates and updates["embedding_dimensions"] is not None:
        current = await repo.get_llm_settings()
        old_dim = 1536
        if current:
            old_dim = current.get("embedding_dimensions", 1536)
        new_dim = updates["embedding_dimensions"]
        if new_dim != old_dim:
            try:
                from app.modules.ai.embedding_migration import migrate_embedding_dimensions
                await migrate_embedding_dimensions(new_dim)
            except Exception:
                logger.exception("Embedding dimension migration failed")

    return _serialize(await repo.upsert_llm_settings(updates))


async def list_prompts() -> list[dict]:
    prompts = await repo.list_prompts()
    return [_serialize(p) for p in prompts]


async def update_prompt(intent: str, template: str) -> dict:
    return _serialize(await repo.upsert_prompt(intent, template))


def _serialize(doc: dict) -> dict:
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
