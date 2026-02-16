"""Postgres pgvector search operations."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import Select, delete, false, func, insert, or_, select, update

from app.core.database import session_scope
from app.core.db_schema import ai_document_chunks, profile_vectors, table_for_collection

logger = logging.getLogger("cosolvent.vector")


async def upsert_profile_vector(
    profile_id: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> None:
    profile_uuid = _to_uuid(profile_id)
    if profile_uuid is None:
        logger.warning("Invalid profile id for vector upsert", extra={"profile_id": profile_id})
        return

    async with session_scope() as session:
        existing = await session.execute(
            select(profile_vectors.c.id).where(profile_vectors.c.profile_id == profile_uuid)
        )
        existing_row = existing.first()

        if existing_row:
            await session.execute(
                update(profile_vectors)
                .where(profile_vectors.c.profile_id == profile_uuid)
                .values(
                    embedding=embedding,
                    vector_metadata=metadata,
                )
            )
        else:
            await session.execute(
                insert(profile_vectors).values(
                    profile_id=profile_uuid,
                    embedding=embedding,
                    vector_metadata=metadata,
                )
            )
        await session.commit()


async def search_vectors(
    query_embedding: list[float],
    top_k: int = 20,
    filter_dict: dict | None = None,
) -> list[dict[str, Any]]:
    filters = dict(filter_dict or {})
    source = filters.pop("source", None)

    if source == "document":
        return await _search_document_vectors(query_embedding, top_k, filters)
    return await _search_profile_vectors(query_embedding, top_k, filters)


async def search_profile_vectors_strict(
    query_embedding: list[float],
    *,
    participant_types: list[str],
    filters: dict[str, Any] | None = None,
    min_score: float = 0.0,
    offset: int = 0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    profiles = table_for_collection("profiles")
    distance = profile_vectors.c.embedding.cosine_distance(query_embedding)
    similarity = 1 - distance
    score = similarity.label("score")
    stmt: Select[Any] = (
        select(
            profile_vectors.c.profile_id,
            score,
            profile_vectors.c.vector_metadata,
            profiles.c.data.label("profile_data"),
        )
        .select_from(profile_vectors.join(profiles, profiles.c.id == profile_vectors.c.profile_id))
        .where(profiles.c.data["status"].astext == "active")
        .where(profiles.c.data["participant_type"].astext.in_(participant_types))
    )

    if min_score > 0:
        stmt = stmt.where(similarity >= min_score)

    # For strict profile retrieval, apply user-facing filters against canonical profile data
    # to avoid stale vector metadata causing false negatives/positives.
    stmt = _apply_profile_field_filters(stmt, profiles.c.data, filters or {})
    stmt = stmt.order_by(
        score.desc(),
        profiles.c.data["updated_at"].astext.desc(),
        profile_vectors.c.profile_id.asc(),
    )
    stmt = stmt.offset(max(0, offset)).limit(max(1, limit))

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(row.profile_id),
            "score": float(row.score),
            "metadata": row.vector_metadata or {},
            "profile": dict(row.profile_data or {}),
        }
        for row in rows
    ]


async def count_profile_vectors_strict(
    query_embedding: list[float],
    *,
    participant_types: list[str],
    filters: dict[str, Any] | None = None,
    min_score: float = 0.0,
) -> int:
    profiles = table_for_collection("profiles")
    distance = profile_vectors.c.embedding.cosine_distance(query_embedding)
    similarity = 1 - distance
    stmt: Select[Any] = (
        select(func.count())
        .select_from(profile_vectors.join(profiles, profiles.c.id == profile_vectors.c.profile_id))
        .where(profiles.c.data["status"].astext == "active")
        .where(profiles.c.data["participant_type"].astext.in_(participant_types))
    )

    if min_score > 0:
        stmt = stmt.where(similarity >= min_score)

    # Keep count predicate in lockstep with strict search predicate.
    stmt = _apply_profile_field_filters(stmt, profiles.c.data, filters or {})

    async with session_scope() as session:
        value = (await session.execute(stmt)).scalar_one()
    return int(value)


async def delete_profile_vector(profile_id: str) -> None:
    profile_uuid = _to_uuid(profile_id)
    if profile_uuid is None:
        return
    async with session_scope() as session:
        await session.execute(delete(profile_vectors).where(profile_vectors.c.profile_id == profile_uuid))
        await session.commit()


async def _search_profile_vectors(
    query_embedding: list[float],
    top_k: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    distance = profile_vectors.c.embedding.cosine_distance(query_embedding)
    score = (1 - distance).label("score")

    stmt: Select[Any] = select(
        profile_vectors.c.profile_id,
        score,
        profile_vectors.c.vector_metadata,
    ).order_by(distance)

    stmt = _apply_metadata_filters(stmt, profile_vectors.c.vector_metadata, filters)
    stmt = stmt.limit(top_k)

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(row.profile_id),
            "score": float(row.score),
            "metadata": row.vector_metadata or {},
        }
        for row in rows
    ]


async def _search_document_vectors(
    query_embedding: list[float],
    top_k: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    distance = ai_document_chunks.c.embedding.cosine_distance(query_embedding)
    score = (1 - distance).label("score")

    stmt: Select[Any] = select(
        ai_document_chunks.c.id,
        score,
        ai_document_chunks.c.chunk_metadata,
    ).order_by(distance)

    stmt = _apply_metadata_filters(stmt, ai_document_chunks.c.chunk_metadata, filters)
    stmt = stmt.limit(top_k)

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(row.id),
            "score": float(row.score),
            "metadata": row.chunk_metadata or {},
        }
        for row in rows
    ]


def _apply_metadata_filters(stmt: Select[Any], metadata_column: Any, filters: dict[str, Any]) -> Select[Any]:
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                stmt = stmt.where(false())
                continue
            conditions = [_json_field_any_match(metadata_column, key, option) for option in value]
            stmt = stmt.where(or_(*conditions))
        else:
            stmt = stmt.where(_json_field_any_match(metadata_column, key, value))
    return stmt


def _apply_profile_field_filters(stmt: Select[Any], profile_data_column: Any, filters: dict[str, Any]) -> Select[Any]:
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                stmt = stmt.where(false())
                continue
            conditions = [
                _json_field_any_match(profile_data_column["fields"], key, option)
                for option in value
            ]
            stmt = stmt.where(or_(*conditions))
        else:
            stmt = stmt.where(_json_field_any_match(profile_data_column["fields"], key, value))
    return stmt


def _json_field_any_match(column: Any, key: str, value: Any):
    # Supports both scalar fields and array fields with "any-match" semantics.
    return or_(
        column.contains({key: value}),
        column.contains({key: [value]}),
    )


def _to_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
