"""Market-dynamics reporting (roadmap B1.8 'Market Physics Scorecard';
CONVERGENCE.md Phase 6 activity 7 — 'aggregate match quality, deal completion
rates, facilitator utilization, and other metrics').

Everything below is computed from data the engine already persists — no new tables,
no background jobs, no simulation run required.

**Deliberately not included: match density / corridor traffic.** No match is
persisted anywhere in the engine today — discovery is query-time-only vector search,
so a true match-density figure would mean running search over the full population on
every call. That's a real gap (still open), not silently solved here; it needs either
a persisted match log or a background compute job, which is a separate, larger piece
of work than this reporting layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.marketplace_config import MarketplaceConfig
from app.modules.analytics import repository as repo
from app.modules.analytics.schemas import (
    DealFunnel,
    FacilitatorRoleUtilization,
    MarketOverview,
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
