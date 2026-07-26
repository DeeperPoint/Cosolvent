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

    # When the marketplace declares a matching profile for this target, use the
    # config-driven weighted-slot + hard-gate model; otherwise fall back to the
    # legacy semantic + field-overlap blend (keeps existing configs working).
    match_profile = config.discovery.matching.profile_for(resolved_target)

    results: list[dict[str, Any]] = []
    gated: list[dict[str, Any]] = []
    for cand in candidates:
        cand_profile = cand.get("profile", {}) or {}
        cand_fields = cand_profile.get("fields", {}) or {}
        vector_score = float(cand.get("score", 0.0))

        filtered_fields = (
            filter_fields_for_discovery(config, target_schema, cand_fields, candidate_tier)
            if target_schema
            else {}
        )
        entry: dict[str, Any] = {
            "id": cand["id"],
            "participant_type": resolved_target,
            "fields": filtered_fields,
        }

        if match_profile is None:
            overlap = _compute_field_overlap(config.discovery.filter_fields, self_fields, cand_fields)
            composite = VECTOR_WEIGHT * vector_score + FIELD_OVERLAP_WEIGHT * overlap
            entry["score"] = round(composite, 6)
            entry["score_breakdown"] = {
                "vector": round(vector_score, 6),
                "field_overlap": round(overlap, 6),
                "vector_weight": VECTOR_WEIGHT,
                "field_overlap_weight": FIELD_OVERLAP_WEIGHT,
            }
            results.append(entry)
            continue

        # Config-driven scoring: composite = vector_weight·vector + Σ slot.weight·slot_score.
        composite = match_profile.vector_weight * vector_score
        slot_detail: dict[str, Any] = {}
        for slot in match_profile.slots:
            s = _slot_score(slot.comparator, self_fields, cand_fields, slot.fields)
            composite += slot.weight * s
            slot_detail[slot.name] = {"score": round(s, 6), "weight": slot.weight}

        gate_results = _evaluate_gates(cand_fields, match_profile.hard_gates)
        entry["score"] = round(composite, 6)
        entry["score_breakdown"] = {
            "vector": round(vector_score, 6),
            "vector_weight": match_profile.vector_weight,
            "slots": slot_detail,
            "gates": gate_results,
        }

        failures = [g for g in gate_results if not g["passed"]]
        if failures:
            # A hard-gate failure excludes the candidate from the ranked list, but it
            # is returned (flagged, with reasons) so the "why gated out" is visible and
            # a future alternative-compliance layer can act on it.
            entry["gated"] = True
            entry["gate_failures"] = [g["name"] for g in failures]
            gated.append(entry)
        else:
            results.append(entry)

    # Re-sort by the composite score because slots/overlap can reorder candidates
    # that the SQL layer ranked purely by cosine distance.
    results.sort(key=lambda r: (-r["score"], r["id"]))
    gated.sort(key=lambda r: (-r["score"], r["id"]))

    out: dict[str, Any] = {
        "results": results,
        "total": len(results),
        "target_type": resolved_target,
    }
    if match_profile is not None:
        out["gated"] = gated
    return out


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


# ── Config-driven slot scoring & hard gates (GAP-3) ───────────────────────

def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pair_score(comparator: str, a: Any, b: Any) -> float | None:
    """Compare one field on both sides into [0,1]; None when not comparable."""
    if a is None or b is None:
        return None
    if comparator == "jaccard":
        a_set = set(a) if isinstance(a, list) else {a}
        b_set = set(b) if isinstance(b, list) else {b}
        union = a_set | b_set
        return (len(a_set & b_set) / len(union)) if union else None
    if comparator == "numeric_proximity":
        na, nb = _num(a), _num(b)
        if na is None or nb is None:
            return None
        denom = max(abs(na), abs(nb), 1.0)
        return max(0.0, 1.0 - abs(na - nb) / denom)
    # scalar_eq (default)
    return 1.0 if a == b else 0.0


def _slot_score(comparator: str, source_fields: dict[str, Any], cand_fields: dict[str, Any],
                fields: list[str]) -> float:
    """Mean of the per-field comparator scores for the slot's fields present on
    both sides. Returns 0.0 when no field is comparable."""
    scores = [
        s for f in fields
        if (s := _pair_score(comparator, source_fields.get(f), cand_fields.get(f))) is not None
    ]
    return sum(scores) / len(scores) if scores else 0.0


def _check_gate(val: Any, gate: Any) -> tuple[bool, str]:
    op = gate.op
    if op == "present":
        return (val not in (None, "", [])), f"{gate.field} is required"
    if val is None:
        return False, f"{gate.field} is missing"
    if op == "equals":
        return (val == gate.value), f"{gate.field} must equal {gate.value!r} (got {val!r})"
    if op == "in":
        allowed = gate.value if isinstance(gate.value, list) else [gate.value]
        vals = val if isinstance(val, list) else [val]
        return (any(v in allowed for v in vals)), f"{gate.field} must be one of {allowed} (got {val!r})"
    if op in ("gte", "lte"):
        nv, gv = _num(val), _num(gate.value)
        if nv is None or gv is None:
            return False, f"{gate.field} must be numeric to compare {op} {gate.value!r} (got {val!r})"
        ok = nv >= gv if op == "gte" else nv <= gv
        return ok, f"{gate.field} must be {op} {gate.value} (got {val!r})"
    return True, ""


def _evaluate_gates(cand_fields: dict[str, Any], gates: list[Any]) -> list[dict[str, Any]]:
    """Evaluate every hard gate against a candidate's fields; a failed gate carries
    a human-readable reason ('why gated out')."""
    out: list[dict[str, Any]] = []
    for gate in gates:
        passed, reason = _check_gate(cand_fields.get(gate.field), gate)
        out.append({"name": gate.name, "field": gate.field, "passed": passed,
                    "reason": None if passed else reason})
    return out
