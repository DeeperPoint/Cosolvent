"""Search queries against MongoDB profiles collection."""

from __future__ import annotations

from typing import Any

from app.core.database import get_collection


async def search_profiles(
    participant_type: str,
    filters: dict[str, Any] | None = None,
    text_query: str | None = None,
    searchable_fields: list[str] | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[dict]:
    """Search active profiles with optional filters and text matching."""
    query: dict[str, Any] = {
        "participant_type": participant_type,
        "status": "active",
    }

    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                query[f"fields.{key}"] = {"$in": value}
            else:
                query[f"fields.{key}"] = value

    if text_query and searchable_fields:
        # Simple regex-based text search across searchable fields
        or_clauses = []
        for field_name in searchable_fields:
            or_clauses.append({
                f"fields.{field_name}": {"$regex": text_query, "$options": "i"}
            })
        if or_clauses:
            query["$or"] = or_clauses

    cursor = get_collection("profiles").find(query).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def count_profiles(
    participant_type: str,
    filters: dict[str, Any] | None = None,
) -> int:
    query: dict[str, Any] = {
        "participant_type": participant_type,
        "status": "active",
    }
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                query[f"fields.{key}"] = {"$in": value}
            else:
                query[f"fields.{key}"] = value
    return await get_collection("profiles").count_documents(query)
