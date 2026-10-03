"""The deal risk register — derived from the deal's own state, never stored.

Each test states a deal condition and the risk it should raise, because the
register's whole value is that it cannot drift from the deal it describes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.deals import service


async def _risks(view: dict) -> list[dict]:
    with patch.object(service, "_deal_view", new=AsyncMock(return_value=view)):
        return await service.deal_risks("d1", {"_id": "u1"}, config=None)


def _labels(risks: list[dict]) -> set[str]:
    return {r["label"] for r in risks}


@pytest.mark.asyncio
async def test_a_complete_deal_raises_nothing_but_concentration():
    """Two principals is a fact about every bilateral deal, not a defect — it is
    reported at low severity so the register is never empty and never alarmist."""
    risks = await _risks({
        "instrument": "supply_agreement",
        "parties": [{"role": "principal"}, {"role": "principal"}],
        "current_version": {"pending_acknowledgers": [], "template_result": {"missing": []}},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    assert _labels(risks) == {"Single counterparty"}
    assert all(r["severity"] == "low" for r in risks)


@pytest.mark.asyncio
async def test_an_unacknowledged_version_is_raised():
    risks = await _risks({
        "instrument": "x",
        "parties": [],
        "current_version": {"pending_acknowledgers": ["u2", "u3"], "template_result": {}},
    })
    risk = next(r for r in risks if r["label"] == "Unacknowledged version")
    assert "2 party" in risk["detail"]
    assert risk["severity"] == "med"


@pytest.mark.asyncio
async def test_missing_required_fields_scale_with_how_many():
    few = await _risks({"instrument": "x", "parties": [],
                        "current_version": {"template_result": {"missing": ["price"]}}})
    many = await _risks({"instrument": "x", "parties": [],
                         "current_version": {"template_result": {"missing": ["a", "b", "c", "d"]}}})

    assert next(r for r in few if r["label"] == "Incomplete instrument")["severity"] == "med"
    assert next(r for r in many if r["label"] == "Incomplete instrument")["severity"] == "high"


@pytest.mark.asyncio
async def test_no_instrument_means_nothing_governs_completeness():
    risks = await _risks({"instrument": None, "parties": [], "current_version": {}})
    assert "No instrument chosen" in _labels(risks)


@pytest.mark.asyncio
async def test_an_unfilled_facilitator_slot_is_raised():
    risks = await _risks({
        "instrument": "x",
        "parties": [{"status": "needed", "role_type": "inspector"}],
        "current_version": {},
    })
    risk = next(r for r in risks if r["label"] == "Facilitator slot unfilled")
    assert "inspector" in risk["detail"]


@pytest.mark.asyncio
async def test_a_stalled_deal_escalates_with_age():
    recent = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    ancient = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

    stalled = await _risks({"instrument": "x", "parties": [], "current_version": {}, "updated_at": recent})
    long_stalled = await _risks({"instrument": "x", "parties": [], "current_version": {}, "updated_at": ancient})

    assert next(r for r in stalled if r["label"] == "Stalled")["severity"] == "low"
    assert next(r for r in long_stalled if r["label"] == "Stalled")["severity"] == "med"


@pytest.mark.asyncio
async def test_an_unparseable_timestamp_does_not_break_the_register():
    risks = await _risks({"instrument": "x", "parties": [], "current_version": {}, "updated_at": "whenever"})
    assert "Stalled" not in _labels(risks)


@pytest.mark.asyncio
async def test_withheld_attributes_are_reported_as_asymmetry():
    risks = await _risks({
        "instrument": "x", "parties": [],
        "current_version": {"withheld": ["price_floor"]},
    })
    assert "Withheld attributes" in _labels(risks)
