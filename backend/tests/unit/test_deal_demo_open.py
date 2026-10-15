"""Opening a deal in demo mode, when the caller has no counterparty id to use.

The showcase cache a visitor reads withholds counterparty user ids, so a visitor
who signs in as a persona cannot name anyone to deal with. The server picks for
them — and which side it picks from is the part worth pinning down.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.deals import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand, recruiter=facilitator
    return load_marketplace_config(FIXTURES / "talent.yaml")


def _profile(slug, user_id, synthetic=True):
    return {"participant_type": slug, "user_id": user_id, "is_synthetic": synthetic}


def _caller(slug, user_id="caller-1"):
    return {"_id": user_id, "participant_type": slug}


def _listing(by_type):
    async def fake(participant_type, status=None, limit=None):
        return by_type.get(participant_type, [])
    return fake


@pytest.mark.asyncio
async def test_a_supply_caller_is_paired_with_the_demand_side():
    listing = _listing({
        "employer": [_profile("employer", "emp-1")],
        "candidate": [_profile("candidate", "cand-9")],
    })
    created = {}

    async def fake_create(user, body, config):
        created["counterparty"] = body.counterparty_user_id
        return {"id": "deal-1"}

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=fake_create):
        deal = await service.demo_open(_caller("candidate"), _cfg())

    assert created["counterparty"] == "emp-1"
    assert deal["counterparty_participant_type"] == "employer"


@pytest.mark.asyncio
async def test_a_demand_caller_is_paired_with_the_supply_side():
    listing = _listing({"candidate": [_profile("candidate", "cand-3")]})

    async def fake_create(user, body, config):
        return {"id": "deal-2", "counterparty": body.counterparty_user_id}

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=fake_create):
        deal = await service.demo_open(_caller("employer"), _cfg())

    assert deal["counterparty"] == "cand-3"
    assert deal["counterparty_participant_type"] == "candidate"


@pytest.mark.asyncio
async def test_a_facilitator_falls_back_to_either_principal_side():
    """A facilitator has no single opposite, so a principal of either side will do."""
    listing = _listing({"candidate": [_profile("candidate", "cand-7")]})

    async def fake_create(user, body, config):
        return {"id": "deal-3", "counterparty": body.counterparty_user_id}

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=fake_create):
        deal = await service.demo_open(_caller("recruiter"), _cfg())

    assert deal["counterparty"] == "cand-7"


@pytest.mark.asyncio
async def test_a_real_participant_is_never_offered_as_the_counterparty():
    """The whole mechanic rests on every reachable account being synthetic."""
    listing = _listing({"employer": [_profile("employer", "real-1", synthetic=False)]})

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=AsyncMock()):
        with pytest.raises(NotFoundError):
            await service.demo_open(_caller("candidate"), _cfg())


@pytest.mark.asyncio
async def test_the_caller_is_not_paired_with_itself():
    listing = _listing({"employer": [_profile("employer", "caller-1")]})

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=AsyncMock()):
        with pytest.raises(NotFoundError):
            await service.demo_open(_caller("candidate", user_id="caller-1"), _cfg())


@pytest.mark.asyncio
async def test_a_profile_without_an_account_cannot_be_dealt_with():
    """Imported populations are profiles; only some carry a user account."""
    listing = _listing({"employer": [{"participant_type": "employer", "is_synthetic": True}]})

    with patch("app.modules.profiles.repository.list_profiles", new=listing), \
         patch.object(service, "create_deal", new=AsyncMock()):
        with pytest.raises(NotFoundError):
            await service.demo_open(_caller("candidate"), _cfg())


@pytest.mark.asyncio
async def test_an_account_with_no_participant_type_has_no_side_to_deal_from():
    with patch.object(service, "create_deal", new=AsyncMock()):
        with pytest.raises(ForbiddenError):
            await service.demo_open({"_id": "u1", "participant_type": None}, _cfg())
