"""Tests for GAP-11 whole-profile own-voice intake (`POST /{type_slug}/me/extract`).

The extraction mechanism (`service.extract_from_prose`) is participant-type-agnostic — it
reads the caller's schema and applies whatever validates, regardless of role. These tests
exercise it on both sides of the market (supply=candidate, demand=employer) to confirm the
"both sides" half of GAP-11 that had no coverage before: nothing about the code path is
supply-only, but until now nothing proved the demand side actually works.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.profiles import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand, recruiter=facilitator (talent.yaml)
    return load_marketplace_config(FIXTURES / "talent.yaml")


def _profile_response(pid: str, pt: str, fields: dict | None = None) -> dict:
    """Shape returned by `service.get_my_profile` (the `_profile_response` projection —
    keyed by `id`, not `_id`), which is what `extract_from_prose` actually calls."""
    return {
        "id": pid,
        "user_id": "u-1",
        "participant_type": pt,
        "status": "draft",
        "fields": fields or {},
        "completeness": 0,
    }


@pytest.mark.asyncio
async def test_extract_from_prose_applies_canonical_fields_on_demand_side():
    """The demand-side (buyer/employer) half of GAP-11: prose in, canonical fields out,
    same as supply — this is the path that had never actually been exercised."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    profile = _profile_response("p1", "employer")
    extracted = {"company_name": "Acme Robotics", "industry": "Technology"}

    with patch.object(service, "get_my_profile", new=AsyncMock(return_value=profile)), \
         patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=lambda pid, patch_: {**profile, **patch_})), \
         patch.object(service, "_queue_profile_index", new=AsyncMock()), \
         patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value=extracted)):
        result = await service.extract_from_prose(
            user, "We're a Toronto-based robotics manufacturer hiring senior firmware engineers.", _cfg()
        )

    assert set(result["applied"]) == {"company_name", "industry"}
    assert result["jumped"] > 0


@pytest.mark.asyncio
async def test_extract_from_prose_preserves_raw_prose_as_description():
    """Dual representation: the raw prose is always kept verbatim in `description`, even
    though it is never itself sent through the canonical-field validator."""
    user = {"_id": "u-candidate", "participant_type": "candidate"}
    profile = _profile_response("p1", "candidate")
    raw_text = "I'm a backend engineer with 6 years of Python and distributed systems experience."
    captured: dict = {}

    async def _update(pid, patch_):
        captured.update(patch_)
        return {**profile, **patch_}

    with patch.object(service, "get_my_profile", new=AsyncMock(return_value=profile)), \
         patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=_update)), \
         patch.object(service, "_queue_profile_index", new=AsyncMock()), \
         patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value={})):
        await service.extract_from_prose(user, raw_text, _cfg())

    assert captured["fields"]["description"] == raw_text


@pytest.mark.asyncio
async def test_extract_from_prose_skips_invalid_option_values():
    """An extracted value that doesn't match the field's declared options is dropped, not
    coerced or crashed on — the canonical gate stays authoritative over LLM output."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    profile = _profile_response("p1", "employer")
    extracted = {"company_name": "Acme", "industry": "Not A Real Industry"}

    with patch.object(service, "get_my_profile", new=AsyncMock(return_value=profile)), \
         patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=lambda pid, patch_: {**profile, **patch_})), \
         patch.object(service, "_queue_profile_index", new=AsyncMock()), \
         patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value=extracted)):
        result = await service.extract_from_prose(user, "Acme is a technology company.", _cfg())

    assert result["applied"] == ["company_name"]
    assert "industry" not in result["applied"]


@pytest.mark.asyncio
async def test_extract_from_prose_requires_existing_profile():
    user = {"_id": "u-nobody", "participant_type": "employer"}
    with patch.object(service, "get_my_profile", new=AsyncMock(side_effect=NotFoundError("No profile found"))):
        with pytest.raises(NotFoundError):
            await service.extract_from_prose(user, "Some description text here.", _cfg())
