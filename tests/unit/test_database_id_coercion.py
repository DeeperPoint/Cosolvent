from __future__ import annotations

import uuid

from app.core.database import _build_contains_payload, _coerce_uuid


def test_coerce_uuid_accepts_uuid_strings():
    raw = "8d11f8ea-d4da-425f-b9ce-c9964bbf6f9d"
    assert _coerce_uuid(raw) == uuid.UUID(raw)


def test_coerce_uuid_is_stable_for_non_uuid_values():
    first = _coerce_uuid("default")
    second = _coerce_uuid("default")
    assert first == second


def test_build_contains_payload_handles_nested_paths():
    payload = _build_contains_payload("fields.company.name", "Acme")
    assert payload == {"fields": {"company": {"name": "Acme"}}}


def test_build_contains_payload_handles_participant_array_paths():
    payload = _build_contains_payload("participants.user_id", "u-123")
    assert payload == {"participants": [{"user_id": "u-123"}]}
