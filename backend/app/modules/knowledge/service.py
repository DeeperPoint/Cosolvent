"""Reference library service: load + retrieve curated domain chunks.

Loading is idempotent per source document (re-loading a doc replaces its chunks).
Retrieval mirrors discovery's document vector search: cosine similarity + JSONB
metadata filters (vertical, document_type, jurisdiction, ...).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, delete, desc, false, insert, or_, select, update
from sqlalchemy.sql import Select

from app.core.database import session_scope
from app.core.db_schema import knowledge_gap_signals, reference_library

# Stable namespace so non-UUID source ids (e.g. "27_2025") map to a consistent UUID.
_DOC_NS = uuid.UUID("a3f1c2d4-0000-4000-8000-000000000001")


def coerce_doc_id(value: str) -> uuid.UUID:
    """Accept a real UUID string, else derive a deterministic UUID5 from the value."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(_DOC_NS, str(value))


def normalize_record(rec: dict[str, Any], *, default_vertical: str | None = None) -> dict[str, Any]:
    """Validate + normalize one ingestion record into a reference_library row.

    Expected input keys (CommonContext export contract):
      source_doc_id, vertical, chunk_text, embedding, metadata
    Raises ValueError if a required field is missing or malformed.
    """
    chunk_text = rec.get("chunk_text") or rec.get("contextual_content") or rec.get("content")
    if not chunk_text or not str(chunk_text).strip():
        raise ValueError("record missing chunk_text/content")

    embedding = rec.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("record missing embedding vector")

    vertical = rec.get("vertical") or default_vertical
    if not vertical:
        raise ValueError("record missing vertical (and no --vertical default given)")

    source = rec.get("source_doc_id") or rec.get("chunk_id") or rec.get("source")
    if not source:
        raise ValueError("record missing source_doc_id")

    metadata = rec.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "id": uuid.uuid4(),
        "source_doc_id": coerce_doc_id(source),
        "vertical": str(vertical),
        "chunk_text": str(chunk_text),
        "embedding": [float(x) for x in embedding],
        "reference_metadata": metadata,
    }


async def load_reference_records(
    records: list[dict[str, Any]], *, default_vertical: str | None = None
) -> dict[str, int]:
    """Idempotently load reference records. Existing chunks for any referenced
    source_doc_id are deleted first, so re-loading a document replaces it cleanly.
    Returns counts: {"loaded", "documents", "skipped"}."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    for rec in records:
        try:
            rows.append(normalize_record(rec, default_vertical=default_vertical))
        except ValueError:
            skipped += 1

    if not rows:
        return {"loaded": 0, "documents": 0, "skipped": skipped}

    doc_ids = sorted({r["source_doc_id"] for r in rows})
    async with session_scope() as session:
        await session.execute(
            delete(reference_library).where(reference_library.c.source_doc_id.in_(doc_ids))
        )
        await session.execute(insert(reference_library), rows)
        await session.commit()  # session_scope only rolls back; writers must commit

    return {"loaded": len(rows), "documents": len(doc_ids), "skipped": skipped}


def _apply_filters(stmt: Select[Any], filters: dict[str, Any]) -> Select[Any]:
    col = reference_library.c.reference_metadata
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                stmt = stmt.where(false())
                continue
            stmt = stmt.where(or_(*[col[key].astext == str(v) for v in value]))
        else:
            stmt = stmt.where(col[key].astext == str(value))
    return stmt


# Soft preference for curated wiki chunks over raw ones (CommonContext tags each chunk's
# reference_metadata.source_layer = "wiki" | "raw"). A small cosine-distance discount re-ranks
# wiki chunks above raw chunks of comparable relevance, while strong raw matches still surface
# — a hybrid preference, not a hard filter.
PREFERRED_SOURCE_LAYER = "wiki"
SOURCE_LAYER_BOOST = 0.05


async def search_reference_library(
    query_embedding: list[float],
    *,
    top_k: int = 5,
    vertical: str | None = None,
    filters: dict[str, Any] | None = None,
    prefer_source_layer: str | None = PREFERRED_SOURCE_LAYER,
    source_layer_boost: float = SOURCE_LAYER_BOOST,
) -> list[dict[str, Any]]:
    """Metadata-filtered cosine-similarity search over the reference library.

    When ``prefer_source_layer`` is set (default "wiki"), chunks whose
    ``reference_metadata.source_layer`` matches receive a small distance discount so
    curated wiki chunks outrank raw chunks of comparable relevance. This is a soft
    preference: raw chunks remain available as fallback coverage. Pass
    ``source_layer_boost=0`` (or ``prefer_source_layer=None``) to disable.
    """
    distance = reference_library.c.embedding.cosine_distance(query_embedding)
    score = (1 - distance).label("score")

    order_expr: Any = distance
    if prefer_source_layer and source_layer_boost:
        layer = reference_library.c.reference_metadata["source_layer"].astext
        order_expr = distance - case((layer == prefer_source_layer, source_layer_boost), else_=0.0)

    stmt: Select[Any] = select(
        reference_library.c.id,
        reference_library.c.chunk_text,
        reference_library.c.reference_metadata,
        score,
    ).order_by(order_expr)

    if vertical:
        stmt = stmt.where(reference_library.c.vertical == vertical)
    if filters:
        stmt = _apply_filters(stmt, filters)
    stmt = stmt.limit(top_k)

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(row.id),
            "chunk_text": row.chunk_text,
            "metadata": row.reference_metadata or {},
            "score": float(row.score),
        }
        for row in rows
    ]


# ── Loop-2: knowledge gap signals (GAP-14) ───────────────────────────────────
async def record_gap_signal(
    *,
    query: str,
    gap_description: str,
    topic_needed: str = "",
    jurisdiction_needed: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    """Insert a pull-signal row. Non-fatal helper — callers wrap in try/except."""
    async with session_scope() as session:
        result = await session.execute(
            insert(knowledge_gap_signals)
            .values(
                query=query[:1000],
                gap_description=gap_description[:2000],
                topic_needed=topic_needed[:200],
                jurisdiction_needed=jurisdiction_needed[:200],
                metadata=metadata or {},
                status="open",
            )
            .returning(knowledge_gap_signals.c.id)
        )
        new_id = result.scalar_one()
        await session.commit()
    return str(new_id)


async def maybe_record_query_gap(query: str, hits: list[dict[str, Any]], *, threshold: float = 0.35) -> None:
    """Emit a pull-signal when a Q&A can't be answered well: no hits, or the best
    match is below ``threshold``. This is the runtime, query-side half of Loop-2 —
    the market surfacing what knowledge it's missing. Never raises."""
    try:
        top = max((float(h.get("score", 0)) for h in hits), default=0.0)
        if hits and top >= threshold:
            return
        await record_gap_signal(
            query=query,
            gap_description=(
                "A participant asked something the knowledge base could not answer well "
                f"(best match {top:.2f} < {threshold:.2f}). Consider adding a source that covers this."
            ),
            metadata={"source": "query", "top_score": round(top, 3), "hit_count": len(hits)},
        )
    except Exception:  # pragma: no cover - telemetry must never break a query
        pass


async def list_gap_signals(*, status: str | None = "open", limit: int = 100) -> list[dict[str, Any]]:
    stmt = select(knowledge_gap_signals).order_by(desc(knowledge_gap_signals.c.created_at)).limit(limit)
    if status:
        stmt = stmt.where(knowledge_gap_signals.c.status == status)
    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "query": r.query,
            "topic_needed": r.topic_needed,
            "jurisdiction_needed": r.jurisdiction_needed,
            "gap_description": r.gap_description,
            "metadata": r.metadata or {},
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def set_gap_status(gap_id: str, status: str) -> bool:
    async with session_scope() as session:
        result = await session.execute(
            update(knowledge_gap_signals)
            .where(knowledge_gap_signals.c.id == uuid.UUID(gap_id))
            .values(status=status)
        )
        await session.commit()
    return bool(result.rowcount)
