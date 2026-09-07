"""Tests for escape-hatch structured route provenance (granting_authority, edition,
evidence_status) — the schema contract and the row-mapping function, both pure."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.knowledge.schemas import EscapeHatchCreate
from app.modules.knowledge.service import _hatch_row

CONDITION = {"field": "certification", "op": "equals", "value": "CWB W59-002"}


class TestEscapeHatchCreateSchema:
    def test_defaults_to_unconfirmed_with_no_citation(self):
        body = EscapeHatchCreate(gate_name="nadcap_subscope", condition=CONDITION)
        assert body.evidence_status == "unconfirmed"
        assert body.granting_authority is None
        assert body.edition is None

    def test_accepts_a_fully_cited_route(self):
        body = EscapeHatchCreate(
            gate_name="nadcap_subscope",
            condition=CONDITION,
            granting_authority="UL 9540A Ed. 4 §8.3",
            edition="Ed. 4",
            evidence_status="confirmed",
        )
        assert body.granting_authority == "UL 9540A Ed. 4 §8.3"
        assert body.evidence_status == "confirmed"

    @pytest.mark.parametrize("value", ["confirmed", "unconfirmed", "refuted"])
    def test_accepts_every_documented_evidence_status(self, value):
        body = EscapeHatchCreate(gate_name="g", condition=CONDITION, evidence_status=value)
        assert body.evidence_status == value

    def test_rejects_an_undocumented_evidence_status(self):
        with pytest.raises(ValidationError):
            EscapeHatchCreate(gate_name="g", condition=CONDITION, evidence_status="probably")


class TestHatchRowMapping:
    def _row(self, **overrides):
        base = dict(
            id="11111111-1111-1111-1111-111111111111",
            gate_name="nadcap_subscope",
            condition={"field": "certification", "op": "equals", "value": "x"},
            rationale="holds equivalent accreditation",
            vertical=None,
            status="active",
            granting_authority="UL 9540A Ed. 4 §8.3",
            edition="Ed. 4",
            evidence_status="confirmed",
            hatch_metadata={},
            created_at=datetime(2026, 9, 6, tzinfo=timezone.utc),
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_row_surfaces_provenance_fields(self):
        out = _hatch_row(self._row())
        assert out["granting_authority"] == "UL 9540A Ed. 4 §8.3"
        assert out["edition"] == "Ed. 4"
        assert out["evidence_status"] == "confirmed"

    def test_row_passes_through_null_provenance_for_legacy_rows(self):
        out = _hatch_row(self._row(granting_authority=None, edition=None, evidence_status="unconfirmed"))
        assert out["granting_authority"] is None
        assert out["edition"] is None
        assert out["evidence_status"] == "unconfirmed"
