"""Read-only aggregate queries backing market-dynamics reporting.

Cross-cutting by design: reads `profiles`, `deals`, and `story_versions` directly
rather than importing those modules' service layers — mirroring the existing
`admin/repository.py` pattern, where aggregate stats live beside, not inside, the
modules they summarize.
"""

from __future__ import annotations

from typing import Any

from app.core.database import get_collection


async def profile_counts_by_type(*, status: str = "active") -> dict[str, dict[str, int]]:
    """``{participant_type: {"real": n, "synthetic": n}}`` for profiles in ``status``."""
    docs = await get_collection("profiles").find({"status": status}).to_list(length=100_000)
    counts: dict[str, dict[str, int]] = {}
    for d in docs:
        pt = d.get("participant_type") or "unknown"
        bucket = counts.setdefault(pt, {"real": 0, "synthetic": 0})
        bucket["synthetic" if d.get("is_synthetic") else "real"] += 1
    return counts


async def all_deals(limit: int = 50_000) -> list[dict[str, Any]]:
    return await get_collection("deals").find({}).to_list(length=limit)


async def all_story_version_states(limit: int = 200_000) -> list[str]:
    docs = await get_collection("story_versions").find({}).to_list(length=limit)
    return [d.get("state") or "unknown" for d in docs]


async def active_profile_ids_by_type(participant_type: str, limit: int = 200) -> list[str]:
    docs = await get_collection("profiles").find(
        {"participant_type": participant_type, "status": "active"}
    ).to_list(length=limit)
    return [str(d["_id"]) for d in docs]
