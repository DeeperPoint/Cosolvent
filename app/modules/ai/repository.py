from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.database import get_collection


# ── AI Documents ──────────────────────────────────────────────────────────

async def create_document(filename: str, content: str) -> dict[str, Any]:
    doc = {
        "filename": filename,
        "content": content,
        "status": "QUEUED",
        "chunk_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_collection("ai_documents").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_document(doc_id: str) -> dict[str, Any] | None:
    return await get_collection("ai_documents").find_one({"_id": ObjectId(doc_id)})


async def update_document_status(doc_id: str, status: str, chunk_count: int = 0) -> None:
    update: dict[str, Any] = {"status": status}
    if chunk_count:
        update["chunk_count"] = chunk_count
    await get_collection("ai_documents").update_one(
        {"_id": ObjectId(doc_id)}, {"$set": update}
    )


async def list_documents(skip: int = 0, limit: int = 50) -> list[dict]:
    cursor = get_collection("ai_documents").find().skip(skip).limit(limit).sort("created_at", -1)
    return await cursor.to_list(length=limit)


async def delete_document(doc_id: str) -> None:
    await get_collection("ai_documents").delete_one({"_id": ObjectId(doc_id)})


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
