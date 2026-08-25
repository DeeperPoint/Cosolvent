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


def _raw_profile(pid: str, pt: str, fields: dict | None = None) -> dict:
    """Raw stored document, as `repo.get_profile_by_user` returns it. Extraction reads
    the repository directly (it must also work on a draft, before any profile exists),
    so mocking there rather than at `get_my_profile` matches the real call path."""
    return {
        "_id": pid,
        "user_id": "u-1",
        "participant_type": pt,
        "status": "active",
        "fields": fields or {},
        "completeness": 0,
    }


@pytest.mark.asyncio
async def test_extract_from_prose_applies_canonical_fields_on_demand_side():
    """The demand-side (buyer/employer) half of GAP-11: prose in, canonical fields out,
    same as supply — this is the path that had never actually been exercised."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    profile = _raw_profile("p1", "employer")
    extracted = {
        "company_name": {"value": "Acme Robotics", "confidence": 0.95, "source": "Acme Robotics"},
        "industry": {"value": "Technology", "confidence": 0.9, "source": "robotics manufacturer"},
    }

    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
         patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=lambda pid, patch_: {**profile, **patch_})), \
         patch.object(service, "_queue_profile_index", new=AsyncMock()), \
         patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value=extracted)):
        result = await service.extract_from_prose(
            user, "We're a Toronto-based robotics manufacturer hiring senior firmware engineers.", _cfg()
        )

    assert set(result["applied"]) == {"company_name", "industry"}
    assert result["jumped"] > 0


@pytest.mark.asyncio
async def test_extract_from_prose_preserves_raw_prose_in_intake():
    """Dual representation: the raw submission is kept verbatim in `_intake` regardless
    of what the schema contains, so the nuance half always has the original to read."""
    user = {"_id": "u-candidate", "participant_type": "candidate"}
    profile = _raw_profile("p1", "candidate")
    raw_text = "I'm a backend engineer with 6 years of Python and distributed systems experience."
    captured: dict = {}

    async def _update(pid, patch_):
        captured.update(patch_)
        return {**profile, **patch_}

    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)),          patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=_update)),          patch.object(service, "_queue_profile_index", new=AsyncMock()),          patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value={})):
        await service.extract_from_prose(user, raw_text, _cfg())

    assert captured[service.INTAKE_KEY]["raw_text"] == raw_text
    # `candidate` has no `description` field — extraction must not invent one.
    assert "description" not in captured["fields"]


@pytest.mark.asyncio
async def test_description_is_seeded_when_empty():
    """Where the schema does have a `description`, an empty one is seeded with the prose."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    profile = _raw_profile("p1", "employer")
    raw_text = "Acme Robotics builds warehouse automation systems in Toronto."
    captured: dict = {}

    async def _update(pid, patch_):
        captured.update(patch_)
        return {**profile, **patch_}

    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)),          patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=_update)),          patch.object(service, "_queue_profile_index", new=AsyncMock()),          patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value={})):
        await service.extract_from_prose(user, raw_text, _cfg())

    assert captured["fields"]["description"] == raw_text


@pytest.mark.asyncio
async def test_existing_description_is_never_overwritten():
    """A participant-authored description survives extraction — overwriting it with the
    raw submission destroys text they wrote, and the raw text is in `_intake` anyway."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    authored = "We are a family-owned automation company, founded 1994."
    profile = _raw_profile("p1", "employer", {"description": authored})
    captured: dict = {}

    async def _update(pid, patch_):
        captured.update(patch_)
        return {**profile, **patch_}

    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)),          patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=_update)),          patch.object(service, "_queue_profile_index", new=AsyncMock()),          patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value={})):
        await service.extract_from_prose(user, "Totally different prose about robots.", _cfg())

    assert captured["fields"]["description"] == authored
    assert captured[service.INTAKE_KEY]["raw_text"] == "Totally different prose about robots."


@pytest.mark.asyncio
async def test_extract_from_prose_skips_invalid_option_values():
    """An extracted value that doesn't match the field's declared options is dropped, not
    coerced or crashed on — the canonical gate stays authoritative over LLM output."""
    user = {"_id": "u-employer", "participant_type": "employer"}
    profile = _raw_profile("p1", "employer")
    extracted = {
        "company_name": {"value": "Acme", "confidence": 0.9, "source": "Acme"},
        "industry": {"value": "Not A Real Industry", "confidence": 0.4, "source": "technology"},
    }

    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
         patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=lambda pid, patch_: {**profile, **patch_})), \
         patch.object(service, "_queue_profile_index", new=AsyncMock()), \
         patch("app.modules.profiles.ai_extraction.extract_fields_from_document", new=AsyncMock(return_value=extracted)):
        result = await service.extract_from_prose(user, "Acme is a technology company.", _cfg())

    assert result["applied"] == ["company_name"]
    assert "industry" not in result["applied"]
    # Reported rather than silently dropped — otherwise the field just never appears.
    assert [r["field"] for r in result["rejected"]] == ["industry"]


@pytest.mark.asyncio
async def test_extract_from_prose_requires_existing_profile():
    user = {"_id": "u-nobody", "participant_type": "employer"}
    with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=None)),          patch.object(service.repo, "get_draft", new=AsyncMock(return_value=None)):
        with pytest.raises(NotFoundError):
            await service.extract_from_prose(user, "Some description text here.", _cfg())
