"""Search queries against profiles collection."""

from __future__ import annotations

import re
from typing import Any

from app.core.database import get_collection


async def search_profiles(
    participant_type: str,
    filters: dict[str, Any] | None = None,
    text_query: str | None = None,
    searchable_fields: list[str] | None = None,
    skip: int = 0,
    limit: int | None = 20,
) -> list[dict]:
    """Search active profiles with optional filters and text matching."""
    query = _build_search_query(
        participant_type=participant_type,
        filters=filters,
        text_query=text_query,
        searchable_fields=searchable_fields,
    )
    cursor = get_collection("profiles").find(query).sort("updated_at", -1).sort("_id", 1)
    if skip:
        cursor = cursor.skip(skip)
    if limit is not None:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit)


async def count_profiles(
    participant_type: str,
    filters: dict[str, Any] | None = None,
    text_query: str | None = None,
    searchable_fields: list[str] | None = None,
) -> int:
    query = _build_search_query(
        participant_type=participant_type,
        filters=filters,
        text_query=text_query,
        searchable_fields=searchable_fields,
    )
    return await get_collection("profiles").count_documents(query)


async def get_profiles_by_ids(
    profile_ids: list[str],
    participant_types: list[str] | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    if not profile_ids:
        return []

    query: dict[str, Any] = {
        "_id": {"$in": profile_ids},
        "status": "active",
    }
    if participant_types:
        query["participant_type"] = {"$in": participant_types}
    if filters:
        for key, value in filters.items():
            if isinstance(value, list):
                query[f"fields.{key}"] = {"$in": value}
            else:
                query[f"fields.{key}"] = value
    cursor = get_collection("profiles").find(query).sort("updated_at", -1).sort("_id", 1)
    return await cursor.to_list(length=len(profile_ids))


def _build_search_query(
    *,
    participant_type: str,
    filters: dict[str, Any] | None,
    text_query: str | None,
    searchable_fields: list[str] | None,
) -> dict[str, Any]:
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
        # Regex-based text search across searchable fields.
        # Use full query and token-level terms so multi-word queries still match.
        token_candidates = [text_query.strip()]
        token_candidates.extend(part for part in re.split(r"\s+", text_query.strip()) if part)
        tokens = list(dict.fromkeys(token_candidates))

        or_clauses = []
        for token in tokens:
            escaped = re.escape(token)
            for field_name in searchable_fields:
                or_clauses.append({
                    f"fields.{field_name}": {"$regex": escaped, "$options": "i"}
                })
        if or_clauses:
            query["$or"] = or_clauses

    return query
