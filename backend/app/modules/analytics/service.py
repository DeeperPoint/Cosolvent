"""Market-dynamics reporting (roadmap B1.8 'Market Physics Scorecard';
CONVERGENCE.md Phase 6 activity 7 — 'aggregate match quality, deal completion
rates, facilitator utilization, and other metrics').

Everything below is computed from data the engine already persists — no new tables,
no background jobs, no simulation run required. ``get_match_density`` is the one
exception worth flagging: no match is persisted anywhere in the engine, so it
computes fresh on every call by running pgvector search over a capped sample of the
population (see its docstring for the cost/approximation tradeoffs) — it's
deliberately its own endpoint, not folded into ``get_market_overview``, so a cheap
dashboard load never accidentally pays for it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.marketplace_config import MarketplaceConfig
from app.modules.analytics import repository as repo
from app.modules.analytics.schemas import (
    CorridorDensity,
    DealFunnel,
    FacilitatorRoleUtilization,
    MarketOverview,
    MatchDensity,
    ParticipantCounts,
    StoryHealth,
)

# Facilitator slot statuses that represent unmet demand vs. filled demand.
_UNMET_SLOT_STATUSES = {"needed", "searching"}
_FILLED_SLOT_STATUSES = {"confirmed"}
# Deals in these statuses don't represent live facilitator demand.
_INACTIVE_DEAL_STATUSES = {"closed", "cancelled"}


def _rate(numerator: int, total: int) -> float:
    return round(numerator / total, 4) if total else 0.0


def _counts_to_participants(by_type: dict[str, dict[str, int]]) -> ParticipantCounts:
    real = sum(b["real"] for b in by_type.values())
    synthetic = sum(b["synthetic"] for b in by_type.values())
    return ParticipantCounts(
        total=real + synthetic,
        real=real,
        synthetic=synthetic,
        by_type={pt: b["real"] + b["synthetic"] for pt, b in by_type.items()},
    )


def _deal_funnel(deals: list[dict[str, Any]]) -> DealFunnel:
    total = len(deals)
    by_status: dict[str, int] = {}
    by_instrument: dict[str, int] = {}
    for d in deals:
        status = d.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        instrument = d.get("instrument") or "unset"
        by_instrument[instrument] = by_instrument.get(instrument, 0) + 1

    brief_reached = by_status.get("brief_ready", 0) + by_status.get("handoff", 0)
    handoff = by_status.get("handoff", 0)
    abandoned = by_status.get("closed", 0) + by_status.get("cancelled", 0)
    return DealFunnel(
        total=total,
        by_status=by_status,
        by_instrument=by_instrument,
        brief_reached_rate=_rate(brief_reached, total),
        handoff_rate=_rate(handoff, total),
        abandoned_rate=_rate(abandoned, total),
    )


def _facilitator_utilization(
    deals: list[dict[str, Any]],
    config: MarketplaceConfig,
    supply_by_type: dict[str, int],
) -> list[FacilitatorRoleUtilization]:
    role_types = [pt.slug for pt in config.participant_types if pt.role == "facilitator"]
    needed = dict.fromkeys(role_types, 0)
    confirmed = dict.fromkeys(role_types, 0)

    for d in deals:
        if d.get("status") in _INACTIVE_DEAL_STATUSES:
            continue
        for slot in d.get("facilitator_slots", []):
            role = slot.get("role_type")
            if role not in needed:
                continue  # slot type no longer in config, or malformed — ignore
            slot_status = slot.get("status")
            if slot_status in _UNMET_SLOT_STATUSES:
                needed[role] += 1
            elif slot_status in _FILLED_SLOT_STATUSES:
                confirmed[role] += 1

    return [
        FacilitatorRoleUtilization(
            role_type=r,
            demand_needed=needed[r],
            demand_confirmed=confirmed[r],
            supply_profiles=supply_by_type.get(r, 0),
        )
        for r in role_types
    ]


def _story_health(states: list[str]) -> StoryHealth:
    by_state: dict[str, int] = {}
    for s in states:
        by_state[s] = by_state.get(s, 0) + 1
    return StoryHealth(by_state=by_state)


async def get_market_overview(config: MarketplaceConfig) -> MarketOverview:
    by_type = await repo.profile_counts_by_type(status="active")
    supply_by_type = {pt: b["real"] + b["synthetic"] for pt, b in by_type.items()}

    deals = await repo.all_deals()
    states = await repo.all_story_version_states()

    return MarketOverview(
        generated_at=datetime.now(timezone.utc).isoformat(),
        participants=_counts_to_participants(by_type),
        deals=_deal_funnel(deals),
        facilitators=_facilitator_utilization(deals, config, supply_by_type),
        story_versions=_story_health(states),
    )


# ── match density / corridor traffic ────────────────────────────────────────────

# Per-corridor sample cap on the source side — bounds this to O(sample) pgvector
# queries per corridor rather than O(population) unbounded, since (unlike the rest
# of this module) it isn't a cheap aggregate read.
_DEFAULT_SAMPLE_LIMIT = 200
_MAX_SAMPLE_LIMIT = 500
_CANDIDATES_PER_PROFILE = 50


def _opposite_type_pairs(config: MarketplaceConfig) -> list[tuple[str, str]]:
    """supply -> demand corridors. Facilitators are excluded: they don't have a
    natural 'opposite side' the way principals do, so a facilitator corridor would
    need a different question ("is there enough facilitator supply for the demand
    that exists") — that's GAP-19's facilitator-utilization angle, already covered
    by ``get_market_overview``'s ``facilitators`` field, not this one."""
    supply = [pt.slug for pt in config.participant_types if pt.role == "supply"]
    demand = [pt.slug for pt in config.participant_types if pt.role == "demand"]
    return [(s, d) for s in supply for d in demand]


async def _corridor_density(
    source_type: str, target_type: str, *, threshold: float, sample_limit: int
) -> CorridorDensity:
    from app.modules.discovery import vector_service

    source_ids = await repo.active_profile_ids_by_type(source_type, limit=sample_limit)
    pairs = 0
    isolated = 0
    top_scores: list[float] = []
    sampled = 0
    for pid in source_ids:
        embedding = await vector_service.get_profile_embedding(pid)
        if embedding is None:
            continue  # not indexed yet — excluded from the sample, not counted as isolated
        sampled += 1
        candidates = await vector_service.find_similar_profiles(
            embedding=embedding,
            participant_types=[target_type],
            exclude_profile_ids=[pid],
            min_score=threshold,
            limit=_CANDIDATES_PER_PROFILE,
        )
        pairs += len(candidates)
        if candidates:
            top_scores.append(float(candidates[0].get("score", 0.0)))
        else:
            isolated += 1

    return CorridorDensity(
        source_type=source_type,
        target_type=target_type,
        source_sampled=sampled,
        pairs_above_threshold=pairs,
        isolated_source_profiles=isolated,
        average_top_score=round(sum(top_scores) / len(top_scores), 4) if top_scores else None,
    )


async def get_match_density(
    config: MarketplaceConfig, *, threshold: float = 0.75, sample_limit: int = _DEFAULT_SAMPLE_LIMIT
) -> MatchDensity:
    """Approximate market thickness per supply->demand corridor: for a capped sample
    of active, indexed source-type profiles, count target-type candidates whose raw
    semantic similarity clears ``threshold`` (CONVERGENCE.md's own example: "12
    plausible buyer-seller pairs out of a population of 80").

    This is explicitly an *approximation*, for two reasons:
      1. It uses raw pgvector cosine similarity only — not the GAP-3 weighted-slot /
         hard-gate composite ``suggested_matches`` ranks with. A pair counted here
         could still fail a hard gate in the real matching flow.
      2. Each side is capped at ``sample_limit`` profiles (default 200, max 500) so
         this stays a bounded number of pgvector queries instead of scaling
         unboundedly with population size.
    Treat the result as an upper-bound signal ("is this corridor thin or thick"),
    not a precise match count.
    """
    sample_limit = max(1, min(int(sample_limit), _MAX_SAMPLE_LIMIT))
    corridors = [
        await _corridor_density(source_type, target_type, threshold=threshold, sample_limit=sample_limit)
        for source_type, target_type in _opposite_type_pairs(config)
    ]
    return MatchDensity(
        generated_at=datetime.now(timezone.utc).isoformat(),
        threshold=threshold,
        corridors=corridors,
    )
