"""Unified search pipeline with config-driven access controls and retrieval modes."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.exceptions import AppError, ForbiddenError, NotFoundError, ServiceUnavailableError, UnauthorizedError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.permission_engine import check_permission, has_completed_required_onboarding
from app.engine.visibility_engine import ViewerTier, filter_fields_for_discovery
from app.modules.discovery import repository as repo
from app.modules.discovery.vector_service import (
    count_profile_vectors_strict,
    search_profile_vectors_strict,
    search_vectors,
)

logger = logging.getLogger("cosolvent.search")


async def search(
    config: MarketplaceConfig,
    query: str | None = None,
    filters: dict[str, Any] | None = None,
    participant_type: str | None = None,
    viewer: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search profiles using either hybrid retrieval or strict RAG retrieval."""
    viewer_tier = _resolve_discovery_viewer_tier(config, viewer)
    search_types = _resolve_search_types(config, participant_type)
    normalized_filters = dict(filters or {})
    _validate_filters(config, search_types, normalized_filters, viewer_tier)

    ai_cfg = config.discovery.ai
    if ai_cfg.profile_retrieval_mode == "rag_strict":
        docs, total = await _search_rag_strict(
            config=config,
            query=query,
            filters=normalized_filters,
            search_types=search_types,
            page=page,
            page_size=page_size,
        )
    else:
        docs, total = await _search_hybrid(
            config=config,
            query=query,
            filters=normalized_filters,
            search_types=search_types,
        )
        docs = _paginate(docs, page, page_size)

    serialized = []
    for doc in docs:
        schema = config.profile_schemas.get(doc["participant_type"])
        if not schema:
            continue
        filtered_fields = filter_fields_for_discovery(config, schema, doc.get("fields", {}), viewer_tier)
        serialized.append({
            "id": str(doc["id"]),
            "participant_type": doc["participant_type"],
            "fields": filtered_fields,
            "score": doc.get("score"),
            "ai_profile": doc.get("ai_profile") if viewer_tier == "owner" else None,
        })

    return {"results": serialized, "total": total, "page": page, "page_size": page_size}


def _resolve_discovery_viewer_tier(config: MarketplaceConfig, viewer: dict[str, Any] | None) -> ViewerTier:
    if viewer is None:
        if not config.discovery.access.anonymous_search_enabled:
            raise UnauthorizedError("Not authenticated")
        return "anonymous"

    if viewer.get("role") == "admin":
        return "authenticated"

    participant_type = str(viewer.get("participant_type", ""))
    if not check_permission(config, participant_type, "can_search"):
        raise ForbiddenError("Missing permission: can_search")
    if not has_completed_required_onboarding(config, viewer):
        raise ForbiddenError("Complete onboarding before using discovery")
    return "authenticated"


def _resolve_search_types(config: MarketplaceConfig, participant_type: str | None) -> list[str]:
    discoverable_types: list[str] = []
    for type_slug in config.discovery.searchable_types:
        pt = config.get_type(type_slug)
        if pt and pt.permissions.visible_in_search:
            discoverable_types.append(type_slug)

    if participant_type:
        if config.get_type(participant_type) is None:
            raise NotFoundError("Unknown participant type")
        if participant_type not in discoverable_types:
            raise NotFoundError("Participant type is not discoverable")
        return [participant_type]

    return discoverable_types


def _validate_filters(
    config: MarketplaceConfig,
    search_types: list[str],
    filters: dict[str, Any],
    viewer_tier: ViewerTier,
) -> None:
    if not filters:
        return

    allowed = set(config.discovery.filter_fields)
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise AppError(f"Unknown filter fields: {', '.join(unknown)}", status_code=422)

    mode = config.discovery.access.anonymous_filter_mode
    if viewer_tier != "anonymous" or mode == "all":
        return
    if mode == "none":
        raise AppError("Anonymous filtering is disabled", status_code=422)

    # public_only mode
    for filter_key in filters:
        matching_fields = 0
        for type_slug in search_types:
            schema = config.profile_schemas.get(type_slug)
            if not schema:
                continue
            field = schema.get_field(filter_key)
            if field is None:
                continue
            matching_fields += 1
            if field.visibility != "public":
                raise AppError(
                    f"Anonymous filter '{filter_key}' is not allowed (must be public)",
                    status_code=422,
                )
        if matching_fields == 0:
            raise AppError(
                f"Filter '{filter_key}' is not applicable to the selected searchable types",
                status_code=422,
            )


async def _search_hybrid(
    *,
    config: MarketplaceConfig,
    query: str | None,
    filters: dict[str, Any],
    search_types: list[str],
) -> tuple[list[dict[str, Any]], int]:
    searchable_fields_by_type = {
        type_slug: [f.name for f in config.profile_schemas[type_slug].all_fields if f.searchable]
        for type_slug in search_types
        if type_slug in config.profile_schemas
    }

    vector_scores: dict[str, float] = {}
    query_embedding: list[float] | None = None
    if query and config.discovery.ai.vector_search_enabled:
        try:
            from app.modules.ai.embedding_client import get_embedding
            query_embedding = await get_embedding(query)
            vector_filter: dict[str, Any] = {"participant_type": search_types}
            vector_filter.update(filters)
            vector_results = await search_vectors(
                query_embedding,
                top_k=config.discovery.ai.max_vector_candidates,
                filter_dict=vector_filter,
            )
            vector_scores = {row["id"]: float(row["score"]) for row in vector_results}
        except Exception:
            logger.warning("Vector search failed, falling back to lexical ranking", exc_info=True)

    all_docs: list[dict[str, Any]] = []
    for type_slug in search_types:
        searchable_fields = searchable_fields_by_type.get(type_slug, [])
        docs = await repo.search_profiles(
            participant_type=type_slug,
            filters=filters,
            text_query=query,
            searchable_fields=searchable_fields,
            skip=0,
            limit=None,
        )
        for doc in docs:
            doc_id = str(doc["_id"])
            lexical_score = _lexical_score(query, doc.get("fields", {}), searchable_fields)
            vector_score = vector_scores.get(doc_id, 0.0)
            ranking_score = vector_score if query_embedding is not None else lexical_score
            all_docs.append({
                "id": doc_id,
                "participant_type": type_slug,
                "fields": doc.get("fields", {}),
                "score": ranking_score,
                "_vector_score": vector_score,
                "_lexical_score": lexical_score,
                "_updated_at": str(doc.get("updated_at", "")),
            })

    total = 0
    for type_slug in search_types:
        total += await repo.count_profiles(
            participant_type=type_slug,
            filters=filters,
            text_query=query,
            searchable_fields=searchable_fields_by_type.get(type_slug, []),
        )

    _sort_ranked_docs(all_docs)
    return all_docs, total


async def _search_rag_strict(
    *,
    config: MarketplaceConfig,
    query: str | None,
    filters: dict[str, Any],
    search_types: list[str],
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    if not query or not query.strip():
        return [], 0

    if not config.discovery.ai.vector_search_enabled:
        if config.discovery.ai.rag_failure_behavior == "empty":
            return [], 0
        raise ServiceUnavailableError("Discovery retrieval unavailable: vector search is not configured")

    try:
        from app.modules.ai.embedding_client import get_embedding
        query_embedding = await get_embedding(query)
    except Exception as exc:
        if config.discovery.ai.rag_failure_behavior == "empty":
            logger.warning("Embedding generation failed in rag_strict mode", exc_info=True)
            return [], 0
        raise ServiceUnavailableError("Discovery retrieval unavailable: embedding generation failed") from exc

    offset = (page - 1) * page_size

    try:
        total = await count_profile_vectors_strict(
            query_embedding,
            participant_types=search_types,
            filters=filters,
            min_score=config.discovery.ai.profile_similarity_threshold,
        )
        rows = await search_profile_vectors_strict(
            query_embedding,
            participant_types=search_types,
            filters=filters,
            min_score=config.discovery.ai.profile_similarity_threshold,
            offset=offset,
            limit=page_size,
        )
    except Exception as exc:
        if config.discovery.ai.rag_failure_behavior == "empty":
            logger.warning("Vector retrieval failed in rag_strict mode", exc_info=True)
            return [], 0
        raise ServiceUnavailableError("Discovery retrieval unavailable: vector search failed") from exc

    docs = []
    for row in rows:
        profile = row.get("profile", {})
        docs.append({
            "id": row["id"],
            "participant_type": profile.get("participant_type", ""),
            "fields": profile.get("fields", {}),
            "score": float(row.get("score", 0.0)),
            "_vector_score": float(row.get("score", 0.0)),
            "_lexical_score": 0.0,
            "_updated_at": str(profile.get("updated_at", "")),
        })
    _sort_ranked_docs(docs)
    return docs, total


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def _sort_ranked_docs(docs: list[dict[str, Any]]) -> None:
    docs.sort(key=lambda d: str(d.get("id", "")))
    docs.sort(key=lambda d: d.get("_updated_at", ""), reverse=True)
    docs.sort(key=lambda d: float(d.get("_lexical_score", 0.0)), reverse=True)
    docs.sort(key=lambda d: float(d.get("_vector_score", 0.0)), reverse=True)


def _lexical_score(query: str | None, fields: dict[str, Any], searchable_fields: list[str]) -> float:
    if not query:
        return 0.0
    query_text = query.strip()
    if not query_text:
        return 0.0

    token_candidates = [query_text]
    token_candidates.extend(part for part in re.split(r"\s+", query_text) if part)
    tokens = list(dict.fromkeys(token_candidates))

    score = 0.0
    for field_name in searchable_fields:
        value = fields.get(field_name)
        if value is None:
            continue
        haystack = " ".join(str(v) for v in value) if isinstance(value, list) else str(value)
        for token in tokens:
            if re.search(re.escape(token), haystack, flags=re.IGNORECASE):
                score += 1.0
    return score
