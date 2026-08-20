"""Post-handoff bidirectional ratings (roadmap §9.2 reputation system; trust
stage 6 'post-transaction evaluation').

Deliberately scoped small for a first version: a 1-5 score + optional comment per
(deal, rater, ratee), only after a deal reaches ``handoff`` (the successful-
completion terminal state — not ``closed``, which means the deal was abandoned).
No dispute-adjustment, no weighting by deal size, no response-time tracking yet —
those are real future extensions, not silently assumed here.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.modules.reputation import repository as repo
from app.modules.reputation.schemas import RateDealRequest


def _principal_ids(deal: dict[str, Any]) -> set[str]:
    return {p["user_id"] for p in deal.get("parties", []) if p.get("role") == "principal"}


async def rate_deal(deal_id: str, rater: dict[str, Any], req: RateDealRequest) -> dict[str, Any]:
    # Imported lazily to avoid a hard import-time dependency between modules
    # (matches the existing cross-module call pattern in deals/service.py).
    from app.modules.deals import repository as deals_repo

    deal = await deals_repo.get_deal(deal_id)
    if not deal:
        raise NotFoundError("Deal not found")
    if deal.get("status") != "handoff":
        raise ConflictError("Ratings are only allowed after a deal reaches handoff")

    rater_id = str(rater["_id"])
    principals = _principal_ids(deal)
    if rater_id not in principals:
        raise ForbiddenError("Only deal principals may rate this deal")
    if req.ratee_user_id == rater_id:
        raise AppError("Cannot rate yourself", 400)
    if req.ratee_user_id not in principals:
        raise AppError("ratee_user_id must be a principal on this deal", 400)

    rating = await repo.upsert_rating(deal_id, rater_id, req.ratee_user_id, req.score, req.comment)
    return _serialize(rating)


async def get_reputation(user_id: str) -> dict[str, Any]:
    ratings = await repo.list_ratings_for_user(user_id)
    count = len(ratings)
    average = round(sum(r["score"] for r in ratings) / count, 2) if count else None
    recent_comments = [r["comment"] for r in ratings[:10] if r.get("comment")]
    return {
        "user_id": user_id,
        "rating_count": count,
        "average_score": average,
        "recent_comments": recent_comments,
    }


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    if out.get("created_at") is not None:
        out["created_at"] = str(out["created_at"])
    out.pop("updated_at", None)
    return out
