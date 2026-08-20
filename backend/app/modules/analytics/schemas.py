"""Response models for market-dynamics reporting."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParticipantCounts(BaseModel):
    total: int
    real: int
    synthetic: int
    by_type: dict[str, int] = Field(default_factory=dict)


class DealFunnel(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_instrument: dict[str, int] = Field(default_factory=dict)
    # (brief_ready + handoff) / total — how many deals produced a Deal Brief at all.
    brief_reached_rate: float = 0.0
    # handoff / total — how many were acknowledged as complete.
    handoff_rate: float = 0.0
    # (closed + cancelled) / total — abandoned or explicitly called off.
    abandoned_rate: float = 0.0


class FacilitatorRoleUtilization(BaseModel):
    role_type: str
    # facilitator_slots still `needed`/`searching` across non-terminal deals — unmet demand.
    demand_needed: int
    # facilitator_slots `confirmed` across non-terminal deals.
    demand_confirmed: int
    # active facilitator profiles of this type — the supply side of the same ratio.
    supply_profiles: int


class StoryHealth(BaseModel):
    # story_versions grouped by lifecycle state (draft/published/milestone/blocked/
    # stale/superseded) — a rough proxy for how much deal activity is stalled.
    by_state: dict[str, int] = Field(default_factory=dict)


class MarketOverview(BaseModel):
    generated_at: str
    participants: ParticipantCounts
    deals: DealFunnel
    facilitators: list[FacilitatorRoleUtilization] = Field(default_factory=list)
    story_versions: StoryHealth
