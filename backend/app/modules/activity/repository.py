"""Storage for the market's activity record.

Append-only by design: an event is a statement that something happened, so
nothing here updates or deletes. The same rows serve two readers — the market
feed, and the audit trail of one subject (a profile, a deal, the market itself).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection

_EVENTS = "activity_events"


async def record(doc: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    row = {
        "event_id": str(uuid.uuid4()),
        "created_at": now.isoformat(),
        **doc,
    }
    await get_collection(_EVENTS).insert_one(row)
    return row


async def _all() -> list[dict[str, Any]]:
    # The proxy has no sort-by-nested-field, and this collection is small enough
    # to order in Python; newest first is the only order either reader wants.
    docs = await get_collection(_EVENTS).find({}).to_list(length=None)
    return sorted(docs, key=lambda d: str(d.get("created_at", "")), reverse=True)


async def list_events(
    *,
    limit: int = 50,
    public_only: bool = False,
    subject_type: str | None = None,
    subject_id: str | None = None,
    event_prefix: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in await _all():
        if public_only and not doc.get("public"):
            continue
        if subject_type and doc.get("subject_type") != subject_type:
            continue
        if subject_id and str(doc.get("subject_id")) != str(subject_id):
            continue
        if event_prefix and not str(doc.get("event", "")).startswith(event_prefix):
            continue
        out.append(doc)
        if len(out) >= limit:
            break
    return out


async def count() -> int:
    docs = await get_collection(_EVENTS).find({}).to_list(length=None)
    return len(docs)
