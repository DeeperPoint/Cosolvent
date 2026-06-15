"""Database access for the reference library (documents + chunks).

Idempotent upserts keyed on the pipeline's natural keys (doc_key, chunk_id) so
re-loading regenerated content updates in place, and a metadata-pre-filtered
cosine-similarity retrieval over the chunk embeddings.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import Select, delete, false, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from app.core.database import session_scope
from app.core.db_schema import reference_chunks, reference_documents

logger = logging.getLogger("cosolvent.knowledge")


async def upsert_document(
    *,
    doc_key: str,
    vertical: str,
    title: str | None,
    source_document: str | None,
    source_url: str | None,
    doc_metadata: dict[str, Any],
) -> uuid.UUID:
    """Insert or update a reference document by its natural key. Returns its id."""
    stmt = (
        pg_insert(reference_documents)
        .values(
            id=uuid.uuid4(),
            doc_key=doc_key,
            vertical=vertical,
            title=title,
            source_document=source_document,
            source_url=source_url,
            doc_metadata=doc_metadata,
        )
        .on_conflict_do_update(
            index_elements=["doc_key"],
            set_={
                "vertical": vertical,
                "title": title,
                "source_document": source_document,
                "source_url": source_url,
                "doc_metadata": doc_metadata,
                "updated_at": func.now(),
            },
        )
        .returning(reference_documents.c.id)
    )
    async with session_scope() as session:
        result = await session.execute(stmt)
        doc_id = result.scalar_one()
        await session.commit()
    return doc_id


async def upsert_chunks(document_id: uuid.UUID, chunks: list[dict[str, Any]]) -> int:
    """Insert or update chunks by chunk_id. Returns the number upserted."""
    if not chunks:
        return 0

    rows = [
        {
            "id": uuid.uuid4(),
            "document_id": document_id,
            "chunk_id": c["chunk_id"],
            "content": c["content"],
            "contextual_content": c["contextual_content"],
            "embedding": c["embedding"],
            "chunk_metadata": c.get("metadata") or {},
        }
        for c in chunks
    ]

    stmt = pg_insert(reference_chunks).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["chunk_id"],
        set_={
            "document_id": stmt.excluded.document_id,
            "content": stmt.excluded.content,
            "contextual_content": stmt.excluded.contextual_content,
            "embedding": stmt.excluded.embedding,
            "chunk_metadata": stmt.excluded.chunk_metadata,
            "updated_at": func.now(),
        },
    )

    async with session_scope() as session:
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def retrieve(
    query_embedding: list[float],
    *,
    top_k: int = 8,
    filters: dict[str, Any] | None = None,
    vertical: str | None = None,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Metadata-pre-filtered cosine-similarity search over reference chunks.

    Joins each chunk back to its parent document so results carry the citation
    fields (doc_key, title, source_document).
    """
    distance = reference_chunks.c.embedding.cosine_distance(query_embedding)
    similarity = 1 - distance
    score = similarity.label("score")

    stmt: Select[Any] = select(
        reference_chunks.c.chunk_id,
        reference_chunks.c.content,
        reference_chunks.c.contextual_content,
        reference_chunks.c.chunk_metadata,
        reference_documents.c.doc_key,
        reference_documents.c.title,
        reference_documents.c.source_document,
        score,
    ).select_from(
        reference_chunks.join(
            reference_documents,
            reference_documents.c.id == reference_chunks.c.document_id,
        )
    )

    if vertical:
        stmt = stmt.where(reference_documents.c.vertical == vertical)
    if min_score > 0:
        stmt = stmt.where(similarity >= min_score)

    stmt = _apply_metadata_filters(stmt, reference_chunks.c.chunk_metadata, filters or {})
    stmt = stmt.order_by(distance).limit(max(1, top_k))

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return [
        {
            "chunk_id": row.chunk_id,
            "doc_key": row.doc_key,
            "title": row.title,
            "source_document": row.source_document,
            "content": row.content,
            "contextual_content": row.contextual_content,
            "score": float(row.score),
            "metadata": row.chunk_metadata or {},
        }
        for row in rows
    ]


async def delete_document(doc_key: str) -> bool:
    """Delete a document and (via FK cascade) its chunks. Returns True if found."""
    async with session_scope() as session:
        result = await session.execute(
            delete(reference_documents).where(reference_documents.c.doc_key == doc_key)
        )
        await session.commit()
    return (result.rowcount or 0) > 0


async def count_chunks(vertical: str | None = None) -> int:
    stmt: Select[Any] = select(func.count()).select_from(reference_chunks)
    if vertical:
        stmt = (
            select(func.count())
            .select_from(
                reference_chunks.join(
                    reference_documents,
                    reference_documents.c.id == reference_chunks.c.document_id,
                )
            )
            .where(reference_documents.c.vertical == vertical)
        )
    async with session_scope() as session:
        return int((await session.execute(stmt)).scalar_one())


def _apply_metadata_filters(stmt: Select[Any], metadata_column: Any, filters: dict[str, Any]) -> Select[Any]:
    """Apply JSONB containment filters with any-match semantics for list values.

    Mirrors discovery.vector_service so reference-library filtering behaves
    identically to participant search (scalar or array metadata fields).
    """
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


def _json_field_any_match(column: Any, key: str, value: Any):
    # Matches both scalar fields ({key: value}) and array fields ({key: [value]}).
    return or_(
        column.contains({key: value}),
        column.contains({key: [value]}),
    )
