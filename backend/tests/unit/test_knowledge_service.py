"""Unit tests for the reference-library (Knowledge Slot) service — pure logic only.

The DB-touching load/search paths are covered by integration tests; here we test the
record normalization and id coercion that run before any DB call.
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.knowledge.service import coerce_doc_id, normalize_record


def _rec(**over):
    base = {
        "source_doc_id": "27_2025",
        "vertical": "prairie-grain",
        "chunk_text": "GAFTA Contract No. 27 clause 1...",
        "embedding": [0.1, 0.2, 0.3],
        "metadata": {"document_type": "contract", "jurisdiction": ["Canada"]},
    }
    base.update(over)
    return base


def test_normalize_happy_path():
    row = normalize_record(_rec())
    assert row["vertical"] == "prairie-grain"
    assert row["chunk_text"].startswith("GAFTA")
    assert row["embedding"] == [0.1, 0.2, 0.3]
    assert isinstance(row["source_doc_id"], uuid.UUID)
    assert row["reference_metadata"]["document_type"] == "contract"


def test_coerce_doc_id_is_deterministic_for_non_uuid():
    assert coerce_doc_id("27_2025") == coerce_doc_id("27_2025")
    assert coerce_doc_id("27_2025") != coerce_doc_id("other_doc")


def test_coerce_doc_id_passes_through_real_uuid():
    u = str(uuid.uuid4())
    assert str(coerce_doc_id(u)) == u


def test_default_vertical_applied_when_missing():
    rec = _rec()
    del rec["vertical"]
    row = normalize_record(rec, default_vertical="machinery_trade")
    assert row["vertical"] == "machinery_trade"


def test_falls_back_to_content_keys_for_text():
    rec = _rec()
    del rec["chunk_text"]
    rec["contextual_content"] = "context-prefixed chunk body"
    row = normalize_record(rec)
    assert row["chunk_text"] == "context-prefixed chunk body"


@pytest.mark.parametrize("bad", [
    {"embedding": []},          # missing/empty embedding
    {"chunk_text": "   "},      # blank text
    {"embedding": "notalist"},  # wrong type
])
def test_rejects_malformed(bad):
    with pytest.raises(ValueError):
        normalize_record(_rec(**bad))


def test_missing_vertical_and_no_default_raises():
    rec = _rec()
    del rec["vertical"]
    with pytest.raises(ValueError):
        normalize_record(rec)
