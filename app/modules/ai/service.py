"""AI service: RAG query pipeline, follow-ups, document management."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import delete

from app.core.config import settings
from app.core.database import session_scope
from app.core.db_schema import ai_document_chunks
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.queue import enqueue_job
from app.core.marketplace_config import MarketplaceConfig
from app.modules.ai import repository as repo
from app.modules.ai.llm_client import generate
from app.modules.ai.prompt_manager import format_prompt, get_prompt_template
from app.modules.discovery.vector_service import search_vectors


async def query(
    user_id: str,
    query_text: str,
    thread_id: str | None,
    filters: dict | None,
    config: MarketplaceConfig,
) -> dict[str, Any]:
    """RAG query: retrieve relevant context, generate answer."""
    if not config.discovery.ai.rag_query_enabled:
        raise AppError("RAG query is disabled for this marketplace", 400)
    if not settings.openai_api_key:
        raise ServiceUnavailableError("AI retrieval unavailable: OpenAI not configured")

    if not thread_id:
        thread_id = str(uuid.uuid4())

    # Retrieve context from vector store
    context = ""
    try:
        from app.modules.discovery.indexer import _get_embedding

        embedding = await _get_embedding(query_text)
        vector_filter = {"source": "document"}
        if filters:
            vector_filter.update(filters)
        results = await search_vectors(embedding, top_k=5, filter_dict=vector_filter)
        context_parts = [r.get("metadata", {}).get("text", "") for r in results]
        context = "\n\n".join(context_parts)
    except Exception as exc:
        raise ServiceUnavailableError("AI retrieval unavailable: vector search failed") from exc

    # Build prompt
    template = await get_prompt_template("rag_query", config)
    prompt = format_prompt(template, config, context=context, query=query_text)

    # Get conversation history
    thread = await repo.get_chat_thread(thread_id)
    messages = []
    if thread and thread.get("messages"):
        messages = thread["messages"]
    messages.append({"role": "user", "content": prompt})

    # Generate
    answer = await generate(messages)

    # Save to history
    messages.append({"role": "assistant", "content": answer})
    await repo.upsert_chat_thread(thread_id, user_id, messages)

    return {
        "answer": answer,
        "thread_id": thread_id,
    }


async def follow_up(
    thread_id: str,
    config: MarketplaceConfig,
) -> dict[str, Any]:
    """Generate follow-up question suggestions."""
    if not config.discovery.ai.follow_up_suggestions:
        raise AppError("Follow-up suggestions are disabled for this marketplace", 400)
    if not settings.openai_api_key:
        raise ServiceUnavailableError("AI service unavailable: OpenAI API key not configured")

    thread = await repo.get_chat_thread(thread_id)
    if not thread:
        return {"suggestions": []}

    template = await get_prompt_template("follow_up", config)
    prompt = format_prompt(template, config)

    messages = thread.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    raw = await generate(messages)
    try:
        suggestions = json.loads(raw)
    except json.JSONDecodeError:
        suggestions = [raw]

    return {"suggestions": suggestions, "thread_id": thread_id}


async def upload_document(filename: str, content: str) -> dict[str, Any]:
    doc = await repo.create_document(filename, content)
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
    await repo.delete_document(doc_id)


async def get_models() -> list[dict]:
    return [
        {"provider": "openai", "model": "gpt-4o-mini", "description": "Fast, affordable"},
        {"provider": "openai", "model": "gpt-4o", "description": "Most capable"},
        {"provider": "openai", "model": "gpt-4-turbo", "description": "High performance"},
    ]


async def get_llm_settings() -> dict:
    settings = await repo.get_llm_settings()
    return settings or {"model": "gpt-4o-mini", "temperature": 0.7, "max_tokens": 1024}


async def update_llm_settings(updates: dict) -> dict:
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
