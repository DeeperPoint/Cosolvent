"""Persistence for post-handoff bidirectional ratings.

One row per (deal, rater, ratee) triple, upserted in place on resubmission — a
rating is the rater's current assessment, not an append-only log entry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection

_RATINGS = "deal_ratings"


async def upsert_rating(
    deal_id: str, rater_user_id: str, ratee_user_id: str, score: int, comment: str | None
) -> dict[str, Any]:
    ratings = get_collection(_RATINGS)
    now = datetime.now(timezone.utc)
    existing = await ratings.find_one({
        "deal_id": deal_id, "rater_user_id": rater_user_id, "ratee_user_id": ratee_user_id,
    })
    if existing:
        await ratings.update_one(
            {"_id": existing["_id"]},
            {"$set": {"score": score, "comment": comment, "updated_at": now}},
        )
        existing.update({"score": score, "comment": comment, "updated_at": now})
        return existing

    doc = {
        "deal_id": deal_id,
        "rater_user_id": rater_user_id,
        "ratee_user_id": ratee_user_id,
        "score": score,
        "comment": comment,
        "created_at": now,
        "updated_at": now,
    }
    result = await ratings.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _created_at(doc: dict[str, Any]) -> datetime:
    value = doc.get("created_at")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return _EPOCH


async def list_ratings_for_user(user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    docs = await get_collection(_RATINGS).find({"ratee_user_id": user_id}).to_list(length=limit)
    return sorted(docs, key=_created_at, reverse=True)
