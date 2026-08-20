"""Tests for post-handoff bidirectional ratings (roadmap §9.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.modules.reputation import service
from app.modules.reputation.schemas import RateDealRequest


def _deal(status: str = "handoff", principals: list[str] | None = None) -> dict:
    principals = principals if principals is not None else ["seller-1", "buyer-1"]
    return {
        "_id": "deal-1",
        "status": status,
        "parties": [{"user_id": uid, "role": "principal"} for uid in principals],
    }


def _rater(uid: str = "seller-1") -> dict:
    return {"_id": uid}


# ── rate_deal: gating ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_deal_404s_when_deal_missing():
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=None)):
        with pytest.raises(NotFoundError):
            await service.rate_deal("deal-1", _rater(), RateDealRequest(ratee_user_id="buyer-1", score=5))


@pytest.mark.asyncio
async def test_rate_deal_rejects_before_handoff():
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=_deal(status="active"))):
        with pytest.raises(ConflictError, match="handoff"):
            await service.rate_deal("deal-1", _rater(), RateDealRequest(ratee_user_id="buyer-1", score=5))


@pytest.mark.asyncio
async def test_rate_deal_rejects_non_principal_rater():
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=_deal())):
        with pytest.raises(ForbiddenError):
            await service.rate_deal("deal-1", _rater("stranger"), RateDealRequest(ratee_user_id="buyer-1", score=5))


@pytest.mark.asyncio
async def test_rate_deal_rejects_self_rating():
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=_deal())):
        with pytest.raises(AppError, match="yourself"):
            await service.rate_deal("deal-1", _rater("seller-1"), RateDealRequest(ratee_user_id="seller-1", score=5))


@pytest.mark.asyncio
async def test_rate_deal_rejects_ratee_not_on_deal():
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=_deal())):
        with pytest.raises(AppError, match="principal on this deal"):
            await service.rate_deal("deal-1", _rater("seller-1"), RateDealRequest(ratee_user_id="outsider", score=5))


@pytest.mark.asyncio
async def test_rate_deal_succeeds_and_serializes():
    stored = {
        "_id": "r1", "deal_id": "deal-1", "rater_user_id": "seller-1", "ratee_user_id": "buyer-1",
        "score": 4, "comment": "Smooth deal", "created_at": "2026-08-20T00:00:00+00:00",
        "updated_at": "2026-08-20T00:00:00+00:00",
    }
    with patch("app.modules.deals.repository.get_deal", new=AsyncMock(return_value=_deal())), \
         patch("app.modules.reputation.service.repo") as mock_repo:
        mock_repo.upsert_rating = AsyncMock(return_value=stored)
        result = await service.rate_deal(
            "deal-1", _rater("seller-1"), RateDealRequest(ratee_user_id="buyer-1", score=4, comment="Smooth deal")
        )
    mock_repo.upsert_rating.assert_awaited_once_with("deal-1", "seller-1", "buyer-1", 4, "Smooth deal")
    assert result["id"] == "r1"
    assert "updated_at" not in result
    assert result["score"] == 4


# ── get_reputation: aggregation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_reputation_with_no_ratings():
    with patch("app.modules.reputation.service.repo") as mock_repo:
        mock_repo.list_ratings_for_user = AsyncMock(return_value=[])
        out = await service.get_reputation("u1")
    assert out == {"user_id": "u1", "rating_count": 0, "average_score": None, "recent_comments": []}


@pytest.mark.asyncio
async def test_get_reputation_averages_scores_and_collects_comments():
    ratings = [
        {"score": 5, "comment": "Great"},
        {"score": 3, "comment": None},
        {"score": 4, "comment": "Good"},
    ]
    with patch("app.modules.reputation.service.repo") as mock_repo:
        mock_repo.list_ratings_for_user = AsyncMock(return_value=ratings)
        out = await service.get_reputation("u1")
    assert out["rating_count"] == 3
    assert out["average_score"] == pytest.approx(4.0)
    assert out["recent_comments"] == ["Great", "Good"]


@pytest.mark.asyncio
async def test_get_reputation_caps_recent_comments_at_ten():
    ratings = [{"score": 5, "comment": f"c{i}"} for i in range(15)]
    with patch("app.modules.reputation.service.repo") as mock_repo:
        mock_repo.list_ratings_for_user = AsyncMock(return_value=ratings)
        out = await service.get_reputation("u1")
    assert len(out["recent_comments"]) == 10
