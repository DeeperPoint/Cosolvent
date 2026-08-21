"""Pre-computation for a public, read-only demo (MarketForge Phase 6a 'Mode 1').

Bakes two things once so a visitor's session never triggers a live vector search
or LLM call:
  1. Per-synthetic-persona top matches (reuses the real suggested_matches scoring
     path — same GAP-3 weighted slots / hard gates / GAP-14 escape hatches a live
     participant would get — not a separate simplified scorer).
  2. Curated knowledge Q&A per participant type (generic template questions —
     "what certifications/standards matter", "what should I know about
     logistics/delivery" — grounded against whatever reference library the
     vertical loaded; deliberately not vertical-specific copy).

Both are stored in ``showcase_cache`` and served by read-only, unauthenticated
endpoints (app/modules/showcase/router.py) — the whole point being that a public
demo link costs nothing per visitor and can't run up an LLM bill or be prompt-
injected, matching CONVERGENCE.md's Phase 6a design.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.marketplace_config import MarketplaceConfig
from app.modules.discovery import matching as discovery_matching
from app.modules.knowledge import service as knowledge_service
from app.modules.profiles import repository as profiles_repo
from app.modules.showcase import repository as repo
from app.modules.showcase.schemas import PrecomputeRunResult

logger = logging.getLogger("cosolvent.showcase")

_MATCHES_PER_PERSONA = 5
_MAX_PERSONAS_PER_TYPE = 30  # bound the precompute job on a large population

# Generic, vertical-agnostic curated prompts (CONVERGENCE.md Phase 6a "Ask about
# this" buttons). Deliberately not hardcoded to any one vertical's vocabulary.
_QA_TEMPLATES = [
    "What certifications, standards, or quality requirements are most relevant for a {label}?",
    "What should a {label} know about logistics, delivery, or fulfillment for a typical deal?",
]


async def _synthetic_profiles(participant_type: str, limit: int) -> list[dict[str, Any]]:
    profiles = await profiles_repo.list_profiles(participant_type, status="active", limit=500)
    return [p for p in profiles if p.get("is_synthetic")][:limit]


async def _precompute_matches_for_type(
    config: MarketplaceConfig, participant_type: str
) -> tuple[int, int, list[str]]:
    personas_cached = 0
    matches_cached = 0
    errors: list[str] = []

    profiles = await _synthetic_profiles(participant_type, _MAX_PERSONAS_PER_TYPE)
    for profile in profiles:
        profile_id = str(profile.get("_id") or profile.get("id"))
        viewer = {"_id": profile["user_id"], "role": "user"}
        try:
            result = await discovery_matching.suggested_matches(
                config, profile_id=profile_id, type_slug=participant_type,
                viewer=viewer, limit=_MATCHES_PER_PERSONA,
            )
        except Exception as exc:  # a profile with no target type / not indexed yet, etc.
            errors.append(f"{participant_type}:{profile_id}: {exc}")
            continue

        await repo.upsert(
            "persona", f"{participant_type}:{profile_id}",
            {"profile_id": profile_id, "participant_type": participant_type, "fields": profile.get("fields", {})},
        )
        personas_cached += 1

        cached_matches = [
            {
                "candidate_profile_id": r["id"],
                "candidate_participant_type": r["participant_type"],
                "fields": r["fields"],
                "score": r["score"],
                "score_breakdown": r.get("score_breakdown", {}),
            }
            for r in result.get("results", [])
        ]
        await repo.upsert("matches", f"{participant_type}:{profile_id}", {"matches": cached_matches})
        matches_cached += 1

    return personas_cached, matches_cached, errors


async def _precompute_qa_for_type(config: MarketplaceConfig, participant_type: str, label: str) -> tuple[int, list[str]]:
    cached = 0
    errors: list[str] = []
    for template in _QA_TEMPLATES:
        query = template.format(label=label)
        try:
            # No vertical filter: `marketplace.yaml`/MarketplaceConfig doesn't retain
            # the domain-schema's vertical slug post-compilation (only display name/
            # description survive `configgen`), and that slug is what reference rows
            # are actually tagged with (`cli load-references --vertical <slug>`) — a
            # display-name filter would silently zero out every result instead of
            # matching, so search the whole (today: single-vertical) library instead.
            res = await knowledge_service.ask(query=query, vertical=None)
        except Exception as exc:
            errors.append(f"qa:{participant_type}: {exc}")
            continue
        await repo.upsert("qa", f"{participant_type}:{query}", {
            "participant_type": participant_type, "query": query,
            "answer": res.answer, "answered": res.answered,
            "citations": [c.model_dump() for c in res.citations],
        })
        cached += 1
    return cached, errors


async def run_precompute(config: MarketplaceConfig) -> PrecomputeRunResult:
    """Regenerate the showcase cache for every configured participant type.
    Idempotent — safe to re-run whenever the population or reference library
    changes; each upsert replaces the prior cached entry for that key."""
    await repo.clear("persona")
    await repo.clear("matches")
    await repo.clear("qa")

    personas_cached = matches_cached = qa_cached = 0
    errors: list[str] = []

    for pt in config.participant_types:
        p, m, errs = await _precompute_matches_for_type(config, pt.slug)
        personas_cached += p
        matches_cached += m
        errors.extend(errs)

        q, errs = await _precompute_qa_for_type(config, pt.slug, pt.name)
        qa_cached += q
        errors.extend(errs)

    logger.info(
        "Showcase precompute: personas=%d matches=%d qa=%d errors=%d",
        personas_cached, matches_cached, qa_cached, len(errors),
    )
    return PrecomputeRunResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        personas_cached=personas_cached, matches_cached=matches_cached,
        qa_cached=qa_cached, errors=errors,
    )


async def get_personas(participant_type: str, limit: int = 30) -> list[dict[str, Any]]:
    return await repo.list_by_kind_prefix("persona", f"{participant_type}:", limit=limit)


async def get_matches(participant_type: str, profile_id: str) -> list[dict[str, Any]]:
    payload = await repo.get("matches", f"{participant_type}:{profile_id}")
    return (payload or {}).get("matches", [])


async def get_qa(participant_type: str) -> list[dict[str, Any]]:
    return await repo.list_by_kind_prefix("qa", f"{participant_type}:", limit=50)
