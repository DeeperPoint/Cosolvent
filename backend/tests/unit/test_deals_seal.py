"""Tests for is_sealed_from — the deal-consent gate on the general profile-view path."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.deals import service

CONFIG = SimpleNamespace(
    story_progression=SimpleNamespace(disclosure_levels=["anonymous", "named", "deal_context"])
)


def _deal(disclosure_level: str, participants: list[str]) -> dict:
    return {
        "_id": "d1",
        "disclosure_level": disclosure_level,
        "participants": [{"user_id": uid} for uid in participants],
        "parties": [{"user_id": uid, "role": "principal", "status": "active"} for uid in participants],
    }


@pytest.mark.asyncio
async def test_same_user_is_never_sealed_from_themselves():
    assert await service.is_sealed_from("u1", "u1", CONFIG) is False


@pytest.mark.asyncio
async def test_sealed_when_shared_deal_has_not_reached_final_disclosure():
    deals = [_deal("anonymous", ["u1", "u2"])]
    with patch("app.modules.deals.repository.list_deals_for_user", new=AsyncMock(return_value=deals)):
        assert await service.is_sealed_from("u1", "u2", CONFIG) is True


@pytest.mark.asyncio
async def test_not_sealed_once_disclosure_reaches_final_level():
    deals = [_deal("deal_context", ["u1", "u2"])]
    with patch("app.modules.deals.repository.list_deals_for_user", new=AsyncMock(return_value=deals)):
        assert await service.is_sealed_from("u1", "u2", CONFIG) is False


@pytest.mark.asyncio
async def test_not_sealed_when_no_shared_deal_exists():
    deals = [_deal("anonymous", ["u1", "u3"])]  # owner "u2" is not a party to any of the viewer's deals
    with patch("app.modules.deals.repository.list_deals_for_user", new=AsyncMock(return_value=deals)):
        assert await service.is_sealed_from("u1", "u2", CONFIG) is False


@pytest.mark.asyncio
async def test_sealed_survives_a_cancelled_deal_that_never_reached_reveal():
    deal = _deal("anonymous", ["u1", "u2"])
    deal["status"] = "cancelled"
    with patch("app.modules.deals.repository.list_deals_for_user", new=AsyncMock(return_value=[deal])):
        assert await service.is_sealed_from("u1", "u2", CONFIG) is True
