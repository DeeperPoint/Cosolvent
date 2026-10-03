"""Recording and reading market activity.

`record` is called from the services that change something. It never raises: an
event is a description of work already done, so failing to describe it must not
undo it. Callers therefore do not need to guard their own writes.
"""

from __future__ import annotations

import logging
from typing import Any

from app.modules.activity import repository as repo

logger = logging.getLogger("cosolvent.activity")

# Events safe to show an anonymous visitor: market-level facts about synthetic
# participants, never a real person's actions. Anything else needs a session.
PUBLIC_EVENTS = {
    "population.imported",
    "showcase.precomputed",
    "profile.indexed",
}


async def record(
    event: str,
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    actor_id: str | None = None,
    actor_label: str | None = None,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
    public: bool | None = None,
) -> None:
    try:
        await repo.record({
            "event": event,
            "subject_type": subject_type,
            "subject_id": str(subject_id) if subject_id is not None else None,
            "actor_id": str(actor_id) if actor_id is not None else None,
            "actor_label": actor_label or ("system" if actor_id is None else None),
            "detail": detail,
            "metadata": metadata or {},
            "public": PUBLIC_EVENTS.__contains__(event) if public is None else bool(public),
        })
    except Exception:  # noqa: BLE001 - never fail the caller's work
        logger.exception("Could not record activity event %s", event)


async def market_feed(limit: int = 50, *, public_only: bool = False) -> list[dict[str, Any]]:
    return await repo.list_events(limit=limit, public_only=public_only)


async def subject_trail(
    subject_type: str, subject_id: str, limit: int = 50, *, public_only: bool = False
) -> list[dict[str, Any]]:
    return await repo.list_events(
        limit=limit, subject_type=subject_type, subject_id=subject_id, public_only=public_only
    )
