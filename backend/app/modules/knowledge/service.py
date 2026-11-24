"""Reference library service: load + retrieve curated domain chunks.

Loading is idempotent per source document (re-loading a doc replaces its chunks).
Retrieval mirrors discovery's document vector search: cosine similarity + JSONB
metadata filters (vertical, document_type, jurisdiction, ...).
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import case, delete, desc, false, func, insert, or_, select, update
from sqlalchemy.sql import Select

from app.core.database import session_scope
from app.core.db_schema import escape_hatches, knowledge_gap_signals, reference_library
from app.modules.ai.embedding_client import get_embedding
from app.modules.ai.llm_client import generate
from app.modules.knowledge.schemas import (
    AskResponse,
    Citation,
    GapSignal,
    GapSignalList,
)

logger = logging.getLogger("cosolvent.knowledge")

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
    # Preserve the human-readable source id (e.g. "27_2025") in the metadata: the
    # row's source_doc_id column is coerced to an opaque UUID, so without this the
    # domain-Q&A path would have no readable handle to cite.
    metadata = {**metadata}
    metadata.setdefault("source_doc_id", str(source))

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


# Operators a filter value may use instead of a bare scalar/list.
#   {"field": "x"}                  field = 'x'                    (unchanged)
#   {"field": ["x", "y"]}           field IN ('x','y')             (unchanged)
#   {"field": {"in": [...]}}        field IN (...)
#   {"field": {"not": [...]}}       field IS NULL OR field NOT IN (...)
#
# `not` is the one that was missing, and its absence is why an evidence-class
# convention could be documented but not enforced: a policy of the form "answer
# participant questions, but never cite demo-derived material" is a negation and
# had no expression. See _not_clause for why it is NULL-tolerant.
_FILTER_OPS = ("in", "not")


def _as_values(value: Any) -> list[str]:
    """Normalise a scalar or sequence into a list of comparison strings."""
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]


def _not_clause(column: Any, values: list[str]) -> Any:
    """`column NOT IN values`, treating an absent tag as passing the filter.

    A plain `col != 'demo_invented'` is NULL for any row whose metadata has no
    `evidence_class` key at all, and NULL is not true, so SQL drops the row. Every
    chunk indexed before the governance vocabulary existed is exactly that row, so
    the naive form would silently empty the corpus the first time anyone excluded
    a class — the filter would look like it worked and would in fact be deleting
    the library from every answer.

    An untagged chunk is unclassified, not classified-as-excluded, so it passes.
    Tightening that is a curation job (tag the backlog), not a query-time one.
    """
    return or_(column.is_(None), column.notin_(values))


def _apply_filters(stmt: Select[Any], filters: dict[str, Any]) -> Select[Any]:
    col = reference_library.c.reference_metadata
    for key, value in filters.items():
        if value is None:
            continue
        column = col[key].astext

        if isinstance(value, dict) and any(op in value for op in _FILTER_OPS):
            if "in" in value:
                included = _as_values(value["in"])
                # An explicitly empty allow-list matches nothing, and saying so is
                # better than quietly ignoring the caller's filter.
                stmt = stmt.where(or_(*[column == v for v in included]) if included else false())
            if "not" in value:
                excluded = _as_values(value["not"])
                if excluded:
                    stmt = stmt.where(_not_clause(column, excluded))
            continue

        if isinstance(value, list):
            if not value:
                stmt = stmt.where(false())
                continue
            stmt = stmt.where(or_(*[column == str(v) for v in value]))
        else:
            stmt = stmt.where(column == str(value))
    return stmt


# The default policy for a participant-facing answer. Demo-invented material
# describes nothing real, and generation-only material is seed input for the
# population generator; neither is a fact about this market, so neither may be
# quoted back to a participant. Curators and the operator console can still reach
# both by passing their own filters.
PARTICIPANT_SAFE_FILTERS: dict[str, Any] = {
    "evidence_class": {"not": ["demo_invented"]},
    "purpose": {"not": ["generation"]},
}


def merge_filters(base: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    """Combine two filter maps, unioning `not` sets rather than overwriting them.

    A caller narrowing by topic must not, as a side effect, drop the safety
    exclusions it never mentioned — so an exclusion present in either map survives
    into the result.
    """
    merged: dict[str, Any] = dict(base)
    for key, value in (extra or {}).items():
        current = merged.get(key)
        if (
            isinstance(current, dict)
            and isinstance(value, dict)
            and "not" in current
            and "not" in value
        ):
            merged[key] = {**current, **value,
                           "not": sorted(set(_as_values(current["not"])) | set(_as_values(value["not"])))}
        elif isinstance(current, dict) and "not" in current and not isinstance(value, dict):
            # Caller asked for a positive match on a field that carries an
            # exclusion. Keep both: the exclusion is a floor, not a default.
            merged[key] = {**current, "in": _as_values(value)}
        else:
            merged[key] = value
    return merged


# Soft preference for curated wiki chunks over raw ones (CommonContext tags each chunk's
# reference_metadata.source_layer = "wiki" | "raw"). A small cosine-distance discount re-ranks
# wiki chunks above raw chunks of comparable relevance, while strong raw matches still surface
# — a hybrid preference, not a hard filter.
PREFERRED_SOURCE_LAYER = "wiki"
SOURCE_LAYER_BOOST = 0.05


# ── Hybrid retrieval: vector + lexical, fused by rank ────────────────────────
# Reciprocal Rank Fusion. Each ranker contributes 1/(RRF_K + rank) to a chunk's
# score, so what fuses is rank position, not the raw scores — which is the point:
# a cosine similarity and a ts_rank_cd are not on comparable scales and any
# attempt to weight them directly needs a calibration constant nobody can defend.
#
# k = 60 is the value from the original RRF paper and the usual default. It is
# large relative to the ranks that matter, which flattens the curve near the top:
# positions 1 and 2 differ by about 2 per cent of a point rather than by half of
# one. That is deliberate — it stops a single ranker's first place from deciding
# the fused order on its own, which is the whole reason to fuse.
RRF_K = 60

# How many candidates to pull from each ranker before fusing. A chunk ranked 3rd
# lexically and 40th by vector should still surface; with a pool of top_k only, it
# never enters the fusion at all. The pool is bounded so a large top_k cannot turn
# into an unbounded read.
_RRF_POOL_MULTIPLIER = 5
_RRF_POOL_MIN = 50
_RRF_POOL_MAX = 500


def _candidate_pool(top_k: int) -> int:
    return max(_RRF_POOL_MIN, min(top_k * _RRF_POOL_MULTIPLIER, _RRF_POOL_MAX))


def _scoped(stmt: Select[Any], vertical: str | None, filters: dict[str, Any] | None) -> Select[Any]:
    """Apply the vertical and metadata filters shared by both rankers.

    Both must see exactly the same candidate set. If the lexical side skipped a
    filter, an excluded chunk could be fused back in on its lexical rank alone —
    which would quietly defeat the participant-safe exclusions.
    """
    if vertical:
        stmt = stmt.where(reference_library.c.vertical == vertical)
    if filters:
        stmt = _apply_filters(stmt, filters)
    return stmt


def _row_payload(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "chunk_text": row.chunk_text,
        "metadata": row.reference_metadata or {},
        "score": float(row.score),
    }


async def search_reference_library(
    query_embedding: list[float],
    *,
    query_text: str | None = None,
    top_k: int = 5,
    vertical: str | None = None,
    filters: dict[str, Any] | None = None,
    prefer_source_layer: str | None = PREFERRED_SOURCE_LAYER,
    source_layer_boost: float = SOURCE_LAYER_BOOST,
    lexical: bool = True,
) -> list[dict[str, Any]]:
    """Metadata-filtered hybrid search over the reference library.

    Two rankers run over the same filtered candidate set — cosine similarity over
    the embedding, and ts_rank_cd over the full-text index — and their rank
    positions are fused with RRF. Lexical retrieval is the single best-evidenced
    improvement available for this corpus, whose discriminating tokens are
    contract numbers, grade codes and standard references: terms whose exact form
    carries the meaning and which an embedding blurs into their neighbours.

    ``query_text`` is what the lexical side searches for. Without it there is
    nothing to match on, so retrieval degrades to vector-only — which is the old
    behaviour, and is also what happens for a caller that has only an embedding.

    When ``prefer_source_layer`` is set (default "wiki"), chunks whose
    ``reference_metadata.source_layer`` matches receive a small distance discount
    so curated wiki chunks outrank raw chunks of comparable relevance. The
    discount is applied inside the vector ranking and reaches the fused order
    through it; it is deliberately not added a second time after fusion, which
    would count the same preference twice.

    ``score`` in each result stays what it has always been — cosine similarity —
    so existing callers read it unchanged. The fusion detail is reported
    alongside it in ``fused_score``, ``vector_rank`` and ``lexical_rank``.
    """
    distance = reference_library.c.embedding.cosine_distance(query_embedding)
    score = (1 - distance).label("score")

    order_expr: Any = distance
    if prefer_source_layer and source_layer_boost:
        layer = reference_library.c.reference_metadata["source_layer"].astext
        order_expr = distance - case((layer == prefer_source_layer, source_layer_boost), else_=0.0)

    pool = _candidate_pool(top_k)
    vector_stmt: Select[Any] = _scoped(
        select(
            reference_library.c.id,
            reference_library.c.chunk_text,
            reference_library.c.reference_metadata,
            score,
        ).order_by(order_expr),
        vertical,
        filters,
    ).limit(pool if (lexical and query_text) else top_k)

    async with session_scope() as session:
        vector_rows = (await session.execute(vector_stmt)).all()

        if not (lexical and query_text and query_text.strip()):
            return [_row_payload(row) for row in vector_rows]

        # websearch_to_tsquery never raises on user input — it parses a search-box
        # string and ignores what it cannot use. plainto_/to_tsquery would make a
        # stray quote or operator in a participant's question an error, turning a
        # malformed query into a failed answer instead of a weaker one.
        tsquery = func.websearch_to_tsquery("english", query_text)
        lexical_rank_expr = func.ts_rank_cd(reference_library.c.chunk_tsv, tsquery)
        lexical_stmt: Select[Any] = _scoped(
            select(
                reference_library.c.id,
                reference_library.c.chunk_text,
                reference_library.c.reference_metadata,
                score,
            )
            .where(reference_library.c.chunk_tsv.op("@@")(tsquery))
            .order_by(desc(lexical_rank_expr)),
            vertical,
            filters,
        ).limit(pool)
        lexical_rows = (await session.execute(lexical_stmt)).all()

    return _fuse(vector_rows, lexical_rows, top_k=top_k)


def _fuse(vector_rows: list[Any], lexical_rows: list[Any], *, top_k: int) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion over the two rankers' positions."""
    payloads: dict[str, dict[str, Any]] = {}
    fused: dict[str, float] = {}

    for label, rows in (("vector_rank", vector_rows), ("lexical_rank", lexical_rows)):
        for position, row in enumerate(rows, start=1):
            key = str(row.id)
            payloads.setdefault(key, _row_payload(row))
            payloads[key][label] = position
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + position)

    for key, value in fused.items():
        payloads[key]["fused_score"] = value
        payloads[key].setdefault("vector_rank", None)
        payloads[key].setdefault("lexical_rank", None)

    ranked = sorted(
        payloads.values(),
        # Ties break on cosine similarity: two chunks found by one ranker each, at
        # the same position, are otherwise ordered by dict insertion, which is an
        # accident of which query returned first.
        key=lambda p: (p["fused_score"], p["score"]),
        reverse=True,
    )
    return ranked[:top_k]


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


async def maybe_record_gate_gap(
    *, gate_name: str, gate_reason: str, target_type: str, vertical: str | None = None
) -> None:
    """The match-side half of Loop-2: a candidate is blocked by a hard gate → emit a
    pull signal naming the blocking constraint, so a curator can ingest an escape hatch.

    Deduped: only one *open* signal per gate is kept (matching runs on every read, so an
    un-deduped insert would flood the curation dashboard). Never raises."""
    try:
        async with session_scope() as session:
            existing = await session.execute(
                select(knowledge_gap_signals.c.id).where(
                    knowledge_gap_signals.c.status == "open",
                    knowledge_gap_signals.c.metadata["gate"].astext == gate_name,
                ).limit(1)
            )
            if existing.first() is not None:
                return
            await session.execute(
                insert(knowledge_gap_signals).values(
                    id=uuid.uuid4(),
                    query=f"Match blocked by gate '{gate_name}'",
                    gap_description=(
                        f"Candidates for '{target_type}' are being excluded by the hard gate "
                        f"'{gate_name}' ({gate_reason}). If an alternative-compliance path exists, "
                        f"add an escape hatch so qualifying candidates unlock."
                    ),
                    topic_needed=gate_name,
                    metadata={"source": "match_gate", "gate": gate_name, "target_type": target_type},
                    status="open",
                    vertical=vertical,
                    reason="match_gate_blocked",
                )
            )
            await session.commit()
    except Exception:  # pragma: no cover - telemetry must never break matching
        logger.warning("Failed to record match-gate gap signal", exc_info=True)


# ── Escape hatches: conditional-gate rules (GAP-14 payoff half) ────────────────
async def create_escape_hatch(
    *,
    gate_name: str,
    condition: dict[str, Any],
    rationale: str = "",
    vertical: str | None = None,
    metadata: dict[str, Any] | None = None,
    granting_authority: str | None = None,
    edition: str | None = None,
    evidence_status: str = "unconfirmed",
) -> str:
    async with session_scope() as session:
        result = await session.execute(
            insert(escape_hatches)
            .values(
                id=uuid.uuid4(),
                gate_name=gate_name,
                condition=condition,
                rationale=rationale[:2000],
                vertical=vertical,
                status="active",
                granting_authority=granting_authority,
                edition=edition,
                evidence_status=evidence_status,
                hatch_metadata=metadata or {},
            )
            .returning(escape_hatches.c.id)
        )
        new_id = result.scalar_one()
        await session.commit()
    return str(new_id)


def _hatch_row(r: Any) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "gate_name": r.gate_name,
        "condition": r.condition or {},
        "rationale": r.rationale,
        "vertical": r.vertical,
        "status": r.status,
        "granting_authority": r.granting_authority,
        "edition": r.edition,
        "evidence_status": r.evidence_status,
        "metadata": r.hatch_metadata or {},
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def list_escape_hatches(
    *, status: str | None = "active", vertical: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    stmt = select(escape_hatches).order_by(desc(escape_hatches.c.created_at)).limit(limit)
    if status:
        stmt = stmt.where(escape_hatches.c.status == status)
    if vertical:
        stmt = stmt.where(escape_hatches.c.vertical == vertical)
    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()
    return [_hatch_row(r) for r in rows]


async def active_escape_hatches(vertical: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Active hatches grouped by the gate they condition — the shape the matching
    engine consults. ``vertical=None`` (default) matches every active hatch, which is
    correct for a single-marketplace deployment; a set vertical also lets vertical-less
    (global) hatches through."""
    stmt = select(escape_hatches).where(escape_hatches.c.status == "active")
    if vertical:
        stmt = stmt.where(
            or_(escape_hatches.c.vertical == vertical, escape_hatches.c.vertical.is_(None))
        )
    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r.gate_name, []).append(_hatch_row(r))
    return grouped


async def set_escape_hatch_status(hatch_id: str, status: str) -> bool:
    async with session_scope() as session:
        result = await session.execute(
            update(escape_hatches)
            .where(escape_hatches.c.id == uuid.UUID(hatch_id))
            .values(status=status)
        )
        await session.commit()
    return bool(result.rowcount)
# ── Grounded domain Q&A over the reference library ────────────────────────────

# Sentinel the model must emit when the excerpts cannot answer the question.
_NOT_COVERED = "NOT_COVERED"
_NOT_COVERED_MSG = "This question isn't covered by the current reference library."

_GROUNDING_SYSTEM = (
    "You are a domain reference assistant for a curated knowledge library. "
    "Answer the question using ONLY the reference excerpts provided by the user. "
    "Cite every excerpt you rely on inline using its bracketed key, e.g. [27_2025]. "
    "Do not use any outside or prior knowledge. If the excerpts do not contain "
    f"enough information to answer, reply with exactly: {_NOT_COVERED}"
)

_CITATION_RE = re.compile(r"\[([^\]\n]+)\]")

# A chunk's text may itself begin with a bracketed source marker (e.g.
# "[27_2025.md] 13. PAYMENT > ..."). It is stripped before the excerpt is shown
# so the only bracketed token in an excerpt is its [key] citation tag — otherwise
# the model may cite "[27_2025.md]", which would not map back to a citation key.
_LEADING_MARKER_RE = re.compile(r"^\s*\[[^\]\n]+\]\s*")


def _cite_key(metadata: dict[str, Any], index: int) -> str:
    """A short, human-citable key for a retrieved chunk.

    Prefers the readable source id preserved on ingest, then common source
    fields, and finally a positional fallback so every excerpt always has a key.
    """
    for field in ("source_doc_id", "doc_key", "source"):
        val = metadata.get(field)
        if val:
            return str(val)
    src = metadata.get("source_document")
    if src:
        return PurePosixPath(str(src)).stem
    return f"ref{index + 1}"


def _format_context(hits: list[dict[str, Any]], keys: list[str]) -> str:
    """Render retrieved chunks as keyed excerpts the model can cite by [key]."""
    blocks = []
    for hit, key in zip(hits, keys):
        excerpt = _LEADING_MARKER_RE.sub("", hit["chunk_text"], count=1)
        blocks.append(f"[{key}]\n{excerpt}")
    return "\n\n---\n\n".join(blocks)


def _extract_citations(answer: str, hits: list[dict[str, Any]], keys: list[str]) -> list[Citation]:
    """Map the [key] tokens the model used back to the retrieved chunks."""
    cited = set(_CITATION_RE.findall(answer))
    by_key: dict[str, Citation] = {}
    for hit, key in zip(hits, keys):
        if key not in cited:
            continue
        entry = by_key.get(key)
        if entry is None:
            meta = hit.get("metadata") or {}
            by_key[key] = Citation(
                key=key,
                source_doc_id=meta.get("source_doc_id"),
                chunk_ids=[hit["id"]],
                metadata=meta,
            )
        else:
            entry.chunk_ids.append(hit["id"])
    return list(by_key.values())


async def ask(
    *,
    query: str,
    filters: dict | None = None,
    vertical: str | None = None,
    top_k: int = 8,
    participant_safe: bool = True,
) -> AskResponse:
    """Answer a question strictly from the reference library, with citations.

    Retrieves the best-matching chunks (wiki-preferred), asks the LLM to answer
    using only those excerpts, and — when nothing matches, the model reports the
    answer is not covered, or the answer carries no resolvable citation — records
    a knowledge gap signal for curators and reports ``answered=False``.

    ``participant_safe`` (the default) adds the exclusions in
    PARTICIPANT_SAFE_FILTERS: demo-invented and generation-only material is kept
    out of the retrieved set entirely, rather than being retrieved and hopefully
    not quoted. Curation tooling that needs to see the whole corpus passes False.
    """
    effective = merge_filters(PARTICIPANT_SAFE_FILTERS, filters) if participant_safe else (filters or {})
    embedding = await get_embedding(query)
    # The question itself drives the lexical ranker. This is the whole value of
    # the hybrid for a question like "what does GAFTA 48 say about weighing?":
    # the embedding finds clauses about weighing, and the lexical side is what
    # pins the answer to contract 48 rather than its neighbours.
    hits = await search_reference_library(
        embedding, query_text=query, top_k=top_k, vertical=vertical, filters=effective
    )
    used_chunks = [h["id"] for h in hits]

    if not hits:
        await _record_gap(query, vertical, effective, "no_matching_chunks")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG)

    keys = [_cite_key(h.get("metadata") or {}, i) for i, h in enumerate(hits)]
    messages = [
        {"role": "system", "content": _GROUNDING_SYSTEM},
        {"role": "user", "content": f"Reference excerpts:\n\n{_format_context(hits, keys)}\n\nQuestion: {query}"},
    ]
    raw = (await generate(messages, use_case="rag_query")).strip()

    if raw.upper().startswith(_NOT_COVERED):
        await _record_gap(query, vertical, effective, "model_not_covered")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG, used_chunks=used_chunks)

    citations = _extract_citations(raw, hits, keys)
    if not citations:
        # Prose with no resolvable citation is not a grounded answer under the
        # "grounded, with citations" contract; treat as not covered + log a gap.
        await _record_gap(query, vertical, effective, "answer_without_citation")
        return AskResponse(query=query, answered=False, answer=_NOT_COVERED_MSG, used_chunks=used_chunks)

    return AskResponse(query=query, answered=True, answer=raw, citations=citations, used_chunks=used_chunks)


# ── Knowledge gap signals (curatorial pull loop) ──────────────────────────────

# Upper bound on rows a single gap query may request, so an arbitrary caller-
# supplied limit on the admin endpoint can't trigger an oversized read.
_MAX_GAP_LIMIT = 500


def bounded_gap_limit(limit: int) -> int:
    """Clamp a requested gap-list limit into [1, _MAX_GAP_LIMIT]."""
    return max(1, min(limit, _MAX_GAP_LIMIT))


async def _record_gap(query: str, vertical: str | None, filters: dict | None, reason: str) -> None:
    try:
        async with session_scope() as session:
            await session.execute(
                knowledge_gap_signals.insert().values(
                    id=uuid.uuid4(), query=query, vertical=vertical, filters=filters or {}, reason=reason
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - a gap-logging failure must not break the answer path.
        logger.warning("Failed to record knowledge gap signal", exc_info=True)


async def list_gaps(vertical: str | None = None, limit: int = 100) -> GapSignalList:
    """Curator view: recorded knowledge gaps, newest first."""
    stmt: Select[Any] = select(knowledge_gap_signals).order_by(
        knowledge_gap_signals.c.created_at.desc()
    )
    if vertical:
        stmt = stmt.where(knowledge_gap_signals.c.vertical == vertical)
    stmt = stmt.limit(bounded_gap_limit(limit))

    async with session_scope() as session:
        rows = (await session.execute(stmt)).all()

    return GapSignalList(
        gaps=[
            GapSignal(
                id=str(row.id),
                query=row.query,
                vertical=row.vertical,
                filters=row.filters or {},
                reason=row.reason,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]
    )
