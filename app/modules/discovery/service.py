"""Unified search pipeline: attribute filters + optional vector search + reranking."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.marketplace_config import MarketplaceConfig
from app.engine.visibility_engine import ViewerTier, filter_fields
from app.modules.discovery import repository as repo
from app.modules.discovery.vector_service import search_vectors

logger = logging.getLogger("cosolvent.search")


async def search(
    config: MarketplaceConfig,
    query: str | None = None,
    filters: dict[str, Any] | None = None,
    participant_type: str | None = None,
    viewer_tier: ViewerTier = "anonymous",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Multi-phase search pipeline.

    Phase 1: Determine searchable type(s)
    Phase 2: Attribute filtering via Postgres
    Phase 3: Optional vector search for semantic ranking
    Phase 4: Optional reranking
    Phase 5: Visibility filtering
    """
    searchable_types = config.discovery.searchable_types
    if participant_type and participant_type in searchable_types:
        search_types = [participant_type]
    else:
        search_types = searchable_types

    all_results: list[dict] = []

    for type_slug in search_types:
        schema = config.profile_schemas.get(type_slug)
        if not schema:
            continue

        searchable_field_names = [f.name for f in schema.all_fields if f.searchable]
        skip = (page - 1) * page_size

        # Phase 2: Postgres attribute search
        db_results = await repo.search_profiles(
            participant_type=type_slug,
            filters=filters,
            text_query=query,
            searchable_fields=searchable_field_names,
            skip=skip,
            limit=page_size,
        )

        # Phase 3: Vector search if enabled and query is present
        vector_scores: dict[str, float] = {}
        if query and config.discovery.ai.vector_search_enabled and settings.openai_api_key:
            try:
                from app.modules.discovery.indexer import _get_embedding
                embedding = await _get_embedding(query)
                vector_filter = {"participant_type": type_slug}
                if filters:
                    vector_filter.update(filters)
                vector_results = await search_vectors(embedding, top_k=page_size, filter_dict=vector_filter)
                vector_scores = {r["id"]: r["score"] for r in vector_results}
            except Exception:
                logger.warning("Vector search failed, falling back to DB-only", exc_info=True)

        # Phase 4: Reranking (optional — uses Cohere if configured)
        # For now, merge scores
        for doc in db_results:
            doc_id = str(doc["_id"])
            score = vector_scores.get(doc_id, 0.0)
            doc["_score"] = score

        # Sort by vector score (higher is better)
        db_results.sort(key=lambda d: d.get("_score", 0), reverse=True)

        # Phase 5: Visibility filtering
        for doc in db_results:
            filtered = filter_fields(schema, doc.get("fields", {}), viewer_tier)
            all_results.append({
                "id": str(doc["_id"]),
                "participant_type": type_slug,
                "fields": filtered,
                "score": doc.get("_score"),
                "ai_profile": doc.get("ai_profile"),
            })

    total = 0
    for type_slug in search_types:
        total += await repo.count_profiles(type_slug, filters)

    return {
        "results": all_results,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
