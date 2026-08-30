"""Tests for AI-assisted registration (`POST /{type_slug}/register/extract`).

`service.extract_for_registration` is the anonymous, stateless sibling of
`extract_from_prose`: no account, draft or profile exists yet, so it only reads a
paragraph of prose and returns the field values the registration form should be
pre-filled with. Nothing is persisted here — the applicant reviews the form and
submits it through the normal `register` path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.marketplace_config import load_marketplace_config
from app.modules.profiles import service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    # candidate=supply, employer=demand (both have ai_extraction_enabled: true),
    # recruiter=facilitator (ai_extraction_enabled: false)
    return load_marketplace_config(FIXTURES / "talent.yaml")


@pytest.mark.asyncio
async def test_confident_values_are_returned_as_form_fields():
    extracted = {
        "company_name": {"value": "Acme Robotics", "confidence": 0.95, "source": "Acme Robotics"},
        "industry": {"value": "Technology", "confidence": 0.9, "source": "robotics"},
    }
    with patch(
        "app.modules.profiles.ai_extraction.extract_fields_from_document",
        new=AsyncMock(return_value=extracted),
    ):
        result = await service.extract_for_registration(
            "employer", "Acme Robotics is a Toronto technology company.", _cfg()
        )

    assert result["fields"]["company_name"] == "Acme Robotics"
    assert result["fields"]["industry"] == "Technology"
    assert set(result["filled"]) == {"company_name", "industry"}
    assert result["uncertain"] == []
    # `employer` has an `About` field — the raw prose seeds it.
    assert result["fields"]["description"] == "Acme Robotics is a Toronto technology company."


@pytest.mark.asyncio
async def test_low_confidence_values_prefill_but_are_flagged_uncertain():
    extracted = {
        "company_name": {"value": "Acme", "confidence": 0.95, "source": "Acme"},
        "industry": {"value": "Finance", "confidence": 0.3, "source": ""},
    }
    with patch(
        "app.modules.profiles.ai_extraction.extract_fields_from_document",
        new=AsyncMock(return_value=extracted),
    ):
        result = await service.extract_for_registration("employer", "Acme does money stuff.", _cfg())

    # Pre-filled so the applicant can correct it in place, but called out for review.
    assert result["fields"]["industry"] == "Finance"
    assert result["uncertain"] == ["industry"]
    assert result["filled"] == ["company_name"]


@pytest.mark.asyncio
async def test_out_of_vocabulary_values_are_rejected_not_coerced():
    extracted = {
        "company_name": {"value": "Acme", "confidence": 0.9, "source": "Acme"},
        "industry": {"value": "Not A Real Industry", "confidence": 0.8, "source": "x"},
    }
    with patch(
        "app.modules.profiles.ai_extraction.extract_fields_from_document",
        new=AsyncMock(return_value=extracted),
    ):
        result = await service.extract_for_registration("employer", "Acme is a company.", _cfg())

    assert "industry" not in result["fields"]
    assert [r["field"] for r in result["rejected"]] == ["industry"]


@pytest.mark.asyncio
async def test_multi_select_and_number_fields_coerce():
    extracted = {
        "full_name": {"value": "Jordan Lee", "confidence": 0.9, "source": "Jordan Lee"},
        "title": {"value": "Senior Backend Engineer", "confidence": 0.9, "source": "engineer"},
        "skills": {"value": ["Python", "AWS", "NotASkill"], "confidence": 0.9, "source": "Python, AWS"},
        "experience_years": {"value": "6", "confidence": 0.9, "source": "6 years"},
    }
    with patch(
        "app.modules.profiles.ai_extraction.extract_fields_from_document",
        new=AsyncMock(return_value=extracted),
    ):
        result = await service.extract_for_registration(
            "candidate", "Jordan Lee, senior backend engineer, 6 years, Python and AWS.", _cfg()
        )

    assert result["fields"]["skills"] == ["Python", "AWS"]  # invalid option dropped
    assert result["fields"]["experience_years"] == 6
    # `candidate` has no `description`/`about` field — extraction must not invent one.
    assert "description" not in result["fields"]


@pytest.mark.asyncio
async def test_extraction_disabled_for_type_is_forbidden():
    with pytest.raises(ForbiddenError):
        await service.extract_for_registration("recruiter", "We place engineers at startups.", _cfg())


@pytest.mark.asyncio
async def test_unknown_participant_type_is_not_found():
    with pytest.raises(NotFoundError):
        await service.extract_for_registration("nonexistent", "Some description here.", _cfg())


@pytest.mark.asyncio
async def test_nothing_is_persisted():
    """The anonymous path must never touch the repository — no draft, no profile, no index."""
    with patch(
        "app.modules.profiles.ai_extraction.extract_fields_from_document",
        new=AsyncMock(return_value={}),
    ), patch.object(service.repo, "update_profile", new=AsyncMock()) as upd, \
       patch.object(service.repo, "upsert_draft", new=AsyncMock()) as draft, \
       patch.object(service, "_queue_profile_index", new=AsyncMock()) as idx:
        await service.extract_for_registration("employer", "Acme Robotics, Toronto.", _cfg())

    upd.assert_not_called()
    draft.assert_not_called()
    idx.assert_not_called()
