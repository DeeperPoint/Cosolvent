"""Profile-to-profile suggested matches.

Given an owner's active profile, this service ranks counterpart-type profiles by
combining semantic similarity (pgvector cosine on stored embeddings) with
structured field overlap on the marketplace's configured ``discovery.filter_fields``.

This is not the same surface as ``/api/search``:

- The viewer must be the profile owner or an admin — never anonymous.
- Matching ignores ``visible_in_search``; that flag governs the public catalog.
  Suggested matches are private recommendations whose follow-through still flows
  through the existing ``communication.conversation_rules``.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import AppError, ForbiddenError, NotFoundError, ServiceUnavailableError
from app.core.marketplace_config import MarketplaceConfig
from app.engine.visibility_engine import filter_fields_for_discovery
from app.modules.discovery import vector_service
from app.modules.profiles import repository as profiles_repo

# Composite score weights. Sum to 1.0; tunable per marketplace later (see Cosolvent-ROADMAP.md §4.2).
VECTOR_WEIGHT = 0.7
FIELD_OVERLAP_WEIGHT = 0.3

MAX_LIMIT = 100


async def suggested_matches(
    config: MarketplaceConfig,
    *,
    profile_id: str,
    type_slug: str,
    viewer: dict[str, Any],
    target_type: str | None = None,
    limit: int = 20,
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Return ranked counterpart-type profiles for ``profile_id``.

    Authorization: requires the viewer to own ``profile_id`` or to be an admin.
    Returns at most ``min(limit, MAX_LIMIT)`` candidates, with ``score`` already
    composited from vector similarity and field overlap.
    """
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if not profile or profile.get("participant_type") != type_slug:
        raise NotFoundError("Profile not found")
    if profile.get("status") != "active":
        raise AppError("Suggested matches require an active profile", status_code=409)

    is_owner = str(viewer.get("_id", "")) == str(profile.get("user_id", ""))
    is_admin = viewer.get("role") == "admin"
    if not (is_owner or is_admin):
        raise ForbiddenError("Suggested matches are visible to the profile owner only")

    resolved_target = _resolve_target_type(config, type_slug, target_type)

    if not config.discovery.ai.vector_search_enabled:
        raise ServiceUnavailableError(
            "Suggested matches require vector search; enable discovery.ai.vector_search_enabled"
        )

    embedding = await vector_service.get_profile_embedding(profile_id)
    if embedding is None:
        # Profile exists and is active but the indexer hasn't run yet.
        raise AppError(
            "Profile is not indexed yet; matches will become available after background indexing completes",
            status_code=409,
        )

    safe_limit = max(1, min(int(limit), MAX_LIMIT))
    candidates = await vector_service.find_similar_profiles(
        embedding=embedding,
        participant_types=[resolved_target],
        exclude_profile_ids=[profile_id],
        min_score=max(0.0, float(min_score)),
        limit=safe_limit,
    )

    target_schema = config.profile_schemas.get(resolved_target)
    self_fields = profile.get("fields", {}) or {}

    # Admins see all fields on candidate profiles; owners see counterpart profiles
    # as an authenticated peer (which honors discovery.result_visibility).
    candidate_tier = "owner" if is_admin else "authenticated"

    results: list[dict[str, Any]] = []
    for cand in candidates:
        cand_profile = cand.get("profile", {}) or {}
        cand_fields = cand_profile.get("fields", {}) or {}
        vector_score = float(cand.get("score", 0.0))
        overlap = _compute_field_overlap(
            config.discovery.filter_fields,
            self_fields,
            cand_fields,
        )
        composite = VECTOR_WEIGHT * vector_score + FIELD_OVERLAP_WEIGHT * overlap

        filtered_fields = (
            filter_fields_for_discovery(config, target_schema, cand_fields, candidate_tier)
            if target_schema
            else {}
        )

        results.append(
            {
                "id": cand["id"],
                "participant_type": resolved_target,
                "score": round(composite, 6),
                "score_breakdown": {
                    "vector": round(vector_score, 6),
                    "field_overlap": round(overlap, 6),
                    "vector_weight": VECTOR_WEIGHT,
                    "field_overlap_weight": FIELD_OVERLAP_WEIGHT,
                },
                "fields": filtered_fields,
            }
        )

    # Re-sort by the composite score because field overlap can reorder candidates
    # that the SQL layer ranked purely by cosine distance.
    results.sort(key=lambda r: (-r["score"], r["id"]))
    return {
        "results": results,
        "total": len(results),
        "target_type": resolved_target,
    }


def _resolve_target_type(
    config: MarketplaceConfig,
    source_type_slug: str,
    target_type: str | None,
) -> str:
    """Pick which participant type to score against.

    If ``target_type`` is provided, validate it. Otherwise, default to the first
    participant type whose role is opposite the source's role
    (supply ↔ demand, with facilitators bridging either side).
    """
    source = config.get_type(source_type_slug)
    if source is None:
        raise NotFoundError("Unknown participant type")

    if target_type:
        if config.get_type(target_type) is None:
            raise NotFoundError("Unknown target participant type")
        if target_type == source_type_slug:
            raise AppError(
                "target_type must differ from the requesting profile's type",
                status_code=422,
            )
        return target_type

    opposite = _opposite_roles(source.role)
    for pt in config.participant_types:
        if pt.slug == source_type_slug:
            continue
        if pt.role in opposite:
            return pt.slug

    # Fall back: any other participant type.
    for pt in config.participant_types:
        if pt.slug != source_type_slug:
            return pt.slug

    raise AppError(
        "No counterpart participant types are configured",
        status_code=422,
    )


def _opposite_roles(role: str) -> set[str]:
    if role == "supply":
        return {"demand", "facilitator"}
    if role == "demand":
        return {"supply", "facilitator"}
    # Facilitator: match against either side.
    return {"supply", "demand"}


def _compute_field_overlap(
    filter_fields: list[str],
    source_fields: dict[str, Any],
    candidate_fields: dict[str, Any],
) -> float:
    """Mean overlap across configured filter_fields. Fields absent on either
    side contribute nothing; if no shared fields exist, returns 0.0.

    - Scalar values: 1.0 if equal, else 0.0
    - List values: Jaccard |A ∩ B| / |A ∪ B|
    - Mixed scalar/list: scalar is treated as a single-element set
    """
    if not filter_fields:
        return 0.0

    scores: list[float] = []
    for field_name in filter_fields:
        a = source_fields.get(field_name)
        b = candidate_fields.get(field_name)
        if a is None or b is None:
            continue
        if isinstance(a, list) or isinstance(b, list):
            a_set = set(a) if isinstance(a, list) else {a}
            b_set = set(b) if isinstance(b, list) else {b}
            union = a_set | b_set
            if not union:
                continue
            scores.append(len(a_set & b_set) / len(union))
        else:
            scores.append(1.0 if a == b else 0.0)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)
