"""GAP-11 extraction guarantees beyond the happy path.

Complements `test_profiles_prose_extraction.py`, which covers prose-in/fields-out
on both sides of the market. These cover the properties that make the extraction
trustworthy: values constrained by the schema rather than filtered afterwards,
per-field confidence and provenance, the onboarding gate, and the clarify loop
preferring confirmation over collection.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError, ServiceUnavailableError
from app.core.marketplace_config import load_marketplace_config
from app.modules.profiles import ai_extraction, service

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg():
    return load_marketplace_config(FIXTURES / "talent.yaml")


def _raw_profile(pid: str, pt: str, fields: dict | None = None, intake: dict | None = None) -> dict:
    """Raw stored document, as the repository returns it."""
    doc = {
        "_id": pid,
        "user_id": "u-1",
        "participant_type": pt,
        "status": "active",
        "fields": fields or {},
        "completeness": 0,
    }
    if intake is not None:
        doc[service.INTAKE_KEY] = intake
    return doc


# ── The response schema constrains the model ─────────────────────────────

class TestExtractionSchema:
    def test_select_options_become_an_enum(self):
        """The enum is what makes an out-of-vocabulary value impossible rather than
        something to detect and discard after the fact."""
        schema = ai_extraction.build_extraction_schema(
            [{"name": "industry", "type": "select", "options": ["Technology", "Mining"]}]
        )
        assert schema["properties"]["industry"]["properties"]["value"] == {
            "type": "string",
            "enum": ["Technology", "Mining"],
        }

    def test_multi_select_becomes_an_array_of_enums(self):
        schema = ai_extraction.build_extraction_schema(
            [{"name": "skills", "type": "multi_select", "options": ["Python", "Go"]}]
        )
        value = schema["properties"]["skills"]["properties"]["value"]
        assert value["type"] == "array"
        assert value["items"]["enum"] == ["Python", "Go"]

    def test_number_is_typed_as_a_number(self):
        schema = ai_extraction.build_extraction_schema([{"name": "years", "type": "number"}])
        assert schema["properties"]["years"]["properties"]["value"]["type"] == "number"

    def test_options_free_select_stays_a_plain_string(self):
        schema = ai_extraction.build_extraction_schema([{"name": "x", "type": "select", "options": []}])
        assert schema["properties"]["x"]["properties"]["value"] == {"type": "string"}

    def test_asset_fields_are_excluded(self):
        """Uploads carry no extractable prose value."""
        schema = ai_extraction.build_extraction_schema(
            [{"name": "cv", "type": "file"}, {"name": "certs", "type": "files"}, {"name": "bio", "type": "text"}]
        )
        assert set(schema["properties"]) == {"bio"}

    def test_every_field_carries_confidence_and_source(self):
        """Strict schema mode requires every property to be listed in `required`,
        so all three keys are mandatory rather than just value+confidence."""
        schema = ai_extraction.build_extraction_schema([{"name": "bio", "type": "text"}])
        props = schema["properties"]["bio"]["properties"]
        assert "confidence" in props and "source" in props
        assert schema["properties"]["bio"]["required"] == ["value", "confidence", "source"]

    def test_fields_are_optional_via_nullability(self):
        """A submission legitimately mentions only some fields. Strict mode forbids
        expressing that through `required`, so each field is nullable instead — the
        model returns null for anything the text does not support."""
        schema = ai_extraction.build_extraction_schema([{"name": "bio", "type": "text"}])
        assert schema["required"] == ["bio"]
        assert schema["properties"]["bio"]["type"] == ["object", "null"]

    def test_null_entries_are_dropped(self):
        """A declined field must not land as an empty value on the profile."""
        out = ai_extraction.normalize_extraction({"bio": None, "title": {"value": "Dev", "confidence": 0.9}})
        assert "bio" not in out
        assert out["title"]["value"] == "Dev"

    def test_null_value_inside_an_entry_is_dropped(self):
        out = ai_extraction.normalize_extraction({"bio": {"value": None, "confidence": 0.1, "source": ""}})
        assert out == {}


# ── Response parsing is robust ───────────────────────────────────────────

class TestResponseParsing:
    def test_markdown_fence_is_tolerated(self):
        """A fenced response used to fail the whole extraction."""
        assert ai_extraction._parse('```json\n{"a": 1}\n```') == {"a": 1}

    def test_plain_json_is_parsed(self):
        assert ai_extraction._parse('{"a": 1}') == {"a": 1}

    def test_non_json_raises_clearly(self):
        with pytest.raises(ServiceUnavailableError):
            ai_extraction._parse("I could not find anything.")

    def test_json_array_is_rejected(self):
        with pytest.raises(ServiceUnavailableError):
            ai_extraction._parse("[1, 2]")

    def test_bare_value_shape_is_tolerated(self):
        """A provider that ignores the schema still yields usable output, scored as
        uncertain rather than silently trusted."""
        out = ai_extraction.normalize_extraction({"industry": "Technology"})
        assert out["industry"]["value"] == "Technology"
        assert out["industry"]["confidence"] == 0.5

    def test_structured_shape_is_preserved(self):
        out = ai_extraction.normalize_extraction(
            {"industry": {"value": "Mining", "confidence": 0.91, "source": "we mine"}}
        )
        assert out["industry"] == {"value": "Mining", "confidence": 0.91, "source": "we mine"}

    def test_missing_confidence_defaults_to_uncertain(self):
        out = ai_extraction.normalize_extraction({"x": {"value": "y"}})
        assert out["x"]["confidence"] == 0.5


# ── Onboarding gate ──────────────────────────────────────────────────────

class TestExtractionGate:
    async def test_disabled_type_is_refused(self):
        """`recruiter` has ai_extraction_enabled: false — the operator's choice must hold."""
        user = {"_id": "u-r", "participant_type": "recruiter"}
        with pytest.raises(ForbiddenError, match="not enabled"):
            await service.extract_from_prose(user, "I place engineers at startups.", _cfg())

    async def test_enabled_type_proceeds(self):
        user = {"_id": "u-c", "participant_type": "candidate"}
        profile = _raw_profile("p1", "candidate")
        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
             patch.object(service.repo, "update_profile", new=AsyncMock(return_value=profile)), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()), \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value={}),
             ):
            result = await service.extract_from_prose(user, "Backend engineer, six years.", _cfg())
        assert "applied" in result


# ── Confidence and provenance ────────────────────────────────────────────

class TestConfidenceAndProvenance:
    async def test_provenance_is_stored_per_field(self):
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile("p1", "employer")
        extracted = {
            "company_name": {"value": "Acme", "confidence": 0.97, "source": "Acme Robotics"},
        }
        captured: dict = {}

        async def _update(pid, patch_):
            captured.update(patch_)
            return {**profile, **patch_}

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
             patch.object(service.repo, "update_profile", new=AsyncMock(side_effect=_update)), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()), \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value=extracted),
             ):
            await service.extract_from_prose(user, "Acme Robotics builds robots.", _cfg())

        stored = captured[service.INTAKE_KEY]["fields"]["company_name"]
        assert stored["confidence"] == 0.97
        assert stored["source"] == "Acme Robotics"

    async def test_low_confidence_fields_are_reported(self):
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile("p1", "employer")
        extracted = {
            "company_name": {"value": "Acme", "confidence": 0.95, "source": "Acme"},
            "description": {"value": "Maybe robotics", "confidence": 0.3, "source": "unclear"},
        }

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
             patch.object(service.repo, "update_profile", new=AsyncMock(return_value=profile)), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()), \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value=extracted),
             ):
            result = await service.extract_from_prose(user, "We do something with robots.", _cfg())

        assert result["low_confidence"] == ["description"]
        assert "company_name" not in result["low_confidence"]

    async def test_unknown_field_is_reported_not_ignored(self):
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile("p1", "employer")
        extracted = {"not_a_field": {"value": "x", "confidence": 0.9, "source": "x"}}

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
             patch.object(service.repo, "update_profile", new=AsyncMock(return_value=profile)), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()), \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value=extracted),
             ):
            result = await service.extract_from_prose(user, "Some prose here.", _cfg())

        assert result["rejected"][0]["field"] == "not_a_field"
        assert "schema" in result["rejected"][0]["reason"]


# ── Clarify loop prefers confirmation over collection ────────────────────

class TestClarifyPrefersUncertainty:
    async def test_low_confidence_field_is_asked_about_before_empty_optional(self):
        """A wrong value already in the profile misleads matching now; a missing
        optional field only leaves it thinner."""
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile(
            "p1",
            "employer",
            fields={"company_name": "Acme"},
            intake={"suggested": {"industry": {"value": "Mining", "confidence": 0.25, "source": "we dig"}}},
        )

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)):
            result = await service.next_clarification(user, _cfg())

        assert result["field"] == "industry"
        assert result["current_value"] == "Mining"
        assert result["confidence"] == 0.25
        # A confirmation question, not a collection one.
        assert "is that right?" in result["question"]

    async def test_required_empty_field_still_wins(self):
        """A missing required field blocks onboarding outright, so it outranks a
        merely-uncertain one."""
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile(
            "p1",
            "employer",
            fields={},
            intake={"suggested": {"industry": {"value": "Mining", "confidence": 0.2, "source": "we dig"}}},
        )

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)):
            result = await service.next_clarification(user, _cfg())

        assert result["field"] == "company_name"

    async def test_confident_fields_do_not_trigger_confirmation(self):
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile(
            "p1",
            "employer",
            fields={"company_name": "Acme", "industry": "Mining", "description": "We mine."},
            intake={"fields": {"industry": {"confidence": 0.98, "source": "we mine"}}, "suggested": {}},
        )

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)):
            result = await service.next_clarification(user, _cfg())

        assert result["complete"] is True

    async def test_profile_without_intake_behaves_as_before(self):
        """Profiles predating extraction have no provenance; they must not be treated
        as uncertain."""
        user = {"_id": "u-e", "participant_type": "employer"}
        profile = _raw_profile("p1", "employer", fields={"company_name": "Acme", "industry": "Mining"})

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)):
            result = await service.next_clarification(user, _cfg())

        # Falls through to the first empty field, not a confirmation.
        assert result["field"] == "description"
        assert "current_value" not in result


# ── Provenance survives the response projection ──────────────────────────

class TestIntakeProjection:
    """`_profile_response` is an explicit allowlist, so anything not named there is
    dropped. The clarify loop reads provenance *through* that projection — omitting
    it silently disables confirmation questions while every mocked test still passes.
    """

    def _raw_profile(self, tier_fields: dict, intake: dict) -> dict:
        return {
            "_id": "p1",
            "user_id": "u-1",
            "participant_type": "employer",
            "status": "active",
            "fields": tier_fields,
            "completeness": 50,
            service.INTAKE_KEY: intake,
        }

    def test_owner_sees_intake(self):
        intake = {"raw_text": "we mine", "fields": {"industry": {"confidence": 0.2, "source": "we mine"}}}
        out = service._profile_response(self._raw_profile({"industry": "Mining"}, intake), _cfg(), "owner")
        assert out[service.INTAKE_KEY] == intake

    @pytest.mark.parametrize("tier", ["public", "authenticated"])
    def test_other_viewers_never_see_the_raw_submission(self, tier):
        """Raw prose predates visibility filtering — exposing it would route around it."""
        intake = {"raw_text": "confidential margin detail", "fields": {}}
        out = service._profile_response(self._raw_profile({"industry": "Mining"}, intake), _cfg(), tier)
        assert out[service.INTAKE_KEY] is None
        assert "confidential" not in str(out)

    async def test_clarify_loop_reads_provenance_through_the_real_projection(self):
        """End-to-end guard for the bug this class documents: with the projection in
        the path (not a hand-built dict), a low-confidence field must still be asked about."""
        user = {"_id": "u-1", "participant_type": "employer"}
        raw = self._raw_profile(
            {"company_name": "Acme"},
            {"raw_text": "we dig", "suggested": {"industry": {"value": "Mining", "confidence": 0.2, "source": "we dig"}}},
        )

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=raw)):
            result = await service.next_clarification(user, _cfg())

        assert result["field"] == "industry"
        assert result["confidence"] == 0.2
        assert "is that right?" in result["question"]


# ── Intake works at registration, before a profile exists ────────────────

class TestDraftIntake:
    """A newly registered participant has a draft, not a profile. Own-voice intake is
    meant for exactly that moment — the stories open with someone describing their
    position before any structured profile exists — so extraction must work on either.
    """

    async def test_extraction_enriches_a_draft_when_no_profile_exists(self):
        draft = {
            "_id": "d1",
            "user_id": "u-1",
            "participant_type": "employer",
            "status": "draft",
            "fields": {},
        }
        user = {"_id": "u-1", "participant_type": "employer"}
        extracted = {"company_name": {"value": "Acme", "confidence": 0.9, "source": "Acme"}}
        captured: dict = {}

        class _Drafts:
            async def update_one(self, query, update):
                captured["query"] = query
                captured["set"] = update["$set"]

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=None)), \
             patch.object(service.repo, "get_draft", new=AsyncMock(return_value=draft)), \
             patch.object(service, "get_collection", lambda name: _Drafts()), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()) as index, \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value=extracted),
             ):
            result = await service.extract_from_prose(user, "Acme builds robots.", _cfg())

        assert result["target"] == "draft"
        assert result["applied"] == ["company_name"]
        assert captured["set"]["fields"]["company_name"] == "Acme"
        assert captured["set"][service.INTAKE_KEY]["raw_text"] == "Acme builds robots."
        # A draft is not discoverable yet — indexing one would surface an
        # unsubmitted participant in search.
        index.assert_not_called()

    async def test_profile_is_preferred_when_both_exist(self):
        profile = _raw_profile("p1", "employer")
        user = {"_id": "u-1", "participant_type": "employer"}

        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=profile)), \
             patch.object(service.repo, "get_draft", new=AsyncMock(return_value={"_id": "d1", "fields": {}})) as draft, \
             patch.object(service.repo, "update_profile", new=AsyncMock(return_value=profile)), \
             patch.object(service, "_queue_profile_index", new=AsyncMock()), \
             patch(
                 "app.modules.profiles.ai_extraction.extract_fields_from_document",
                 new=AsyncMock(return_value={}),
             ):
            result = await service.extract_from_prose(user, "Some prose about the company.", _cfg())

        assert result["target"] == "profile"
        draft.assert_not_called()

    async def test_neither_profile_nor_draft_is_a_clear_error(self):
        user = {"_id": "u-nobody", "participant_type": "employer"}
        with patch.object(service.repo, "get_profile_by_user", new=AsyncMock(return_value=None)), \
             patch.object(service.repo, "get_draft", new=AsyncMock(return_value=None)):
            with pytest.raises(NotFoundError, match="register first"):
                await service.extract_from_prose(user, "Some prose here.", _cfg())
