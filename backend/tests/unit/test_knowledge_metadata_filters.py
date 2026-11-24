"""Negative metadata filtering, and the participant-safe default policy.

Filters compile to SQL rather than being matched in Python, so these tests
compile the statement and read the predicate. That is deliberate: the bug worth
guarding against here is a semantic one in SQL's three-valued logic, invisible to
any test that only checks which rows a fake returns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.db_schema import reference_library
from app.modules.knowledge import service


def _compiled(filters: dict) -> str:
    stmt = service._apply_filters(select(reference_library.c.id), filters)
    return str(stmt.compile(dialect=postgresql.dialect(),
                            compile_kwargs={"literal_binds": True}))


# ── The forms that already worked ────────────────────────────────────────────
def test_scalar_filter_is_equality():
    sql = _compiled({"topic": "payment_terms"})
    assert "= 'payment_terms'" in sql


def test_list_filter_is_a_disjunction():
    sql = _compiled({"topic": ["payment_terms", "delivery_terms"]})
    assert "'payment_terms'" in sql and "'delivery_terms'" in sql
    assert " OR " in sql


def test_empty_list_matches_nothing_rather_than_being_ignored():
    assert "false" in _compiled({"topic": []}).lower()


# ── Negation ─────────────────────────────────────────────────────────────────
def test_not_filter_emits_a_not_in():
    sql = _compiled({"evidence_class": {"not": ["demo_invented"]}})
    assert "NOT IN" in sql.upper()
    assert "'demo_invented'" in sql


def test_not_filter_keeps_rows_whose_tag_is_absent():
    """The three-valued-logic trap this exists to avoid.

    `col != 'demo_invented'` is NULL when the row has no evidence_class key, and
    NULL is not true, so SQL drops the row. Every chunk indexed before the
    governance vocabulary existed is exactly that row — so the naive form would
    silently empty the library the first time anyone excluded a class, while
    looking like it worked.
    """
    sql = _compiled({"evidence_class": {"not": ["demo_invented"]}})
    assert "IS NULL" in sql.upper(), "exclusion must tolerate an untagged chunk"
    assert " OR " in sql


def test_in_and_not_compose_on_one_field():
    sql = _compiled({"purpose": {"in": ["reference", "both"], "not": ["generation"]}})
    assert "'reference'" in sql and "'both'" in sql
    assert "NOT IN" in sql.upper()


def test_empty_exclusion_list_excludes_nothing():
    """Asking to exclude nothing is not the same as matching nothing."""
    assert "false" not in _compiled({"evidence_class": {"not": []}}).lower()


def test_a_plain_dict_without_operators_is_not_treated_as_one():
    """Guards the operator sniff: a value that merely happens to be a dict."""
    sql = _compiled({"topic": {"in": ["a"]}})
    assert "'a'" in sql


# ── Merging ──────────────────────────────────────────────────────────────────
def test_merge_unions_exclusions_rather_than_overwriting():
    merged = service.merge_filters(
        {"evidence_class": {"not": ["demo_invented"]}},
        {"evidence_class": {"not": ["provisional"]}},
    )
    assert set(merged["evidence_class"]["not"]) == {"demo_invented", "provisional"}


def test_a_caller_narrowing_a_field_cannot_drop_its_safety_exclusion():
    """The exclusion is a floor, not a default the caller can clear by accident."""
    merged = service.merge_filters(service.PARTICIPANT_SAFE_FILTERS, {"purpose": "reference"})
    assert merged["purpose"]["not"] == ["generation"]
    assert merged["purpose"]["in"] == ["reference"]


def test_merge_passes_unrelated_filters_through():
    merged = service.merge_filters(service.PARTICIPANT_SAFE_FILTERS, {"topic": "payment_terms"})
    assert merged["topic"] == "payment_terms"
    assert merged["evidence_class"] == {"not": ["demo_invented"]}


# ── The default policy on the answer path ────────────────────────────────────
@pytest.mark.asyncio
async def test_ask_excludes_demo_invented_and_generation_by_default():
    search = AsyncMock(return_value=[])
    with patch.object(service, "get_embedding", new=AsyncMock(return_value=[0.0] * 1536)), \
         patch.object(service, "search_reference_library", new=search), \
         patch.object(service, "_record_gap", new=AsyncMock()):
        await service.ask(query="anything", vertical="grain")

    applied = search.await_args.kwargs["filters"]
    assert applied["evidence_class"] == {"not": ["demo_invented"]}
    assert applied["purpose"] == {"not": ["generation"]}


@pytest.mark.asyncio
async def test_curation_tooling_can_opt_out_and_see_everything():
    search = AsyncMock(return_value=[])
    with patch.object(service, "get_embedding", new=AsyncMock(return_value=[0.0] * 1536)), \
         patch.object(service, "search_reference_library", new=search), \
         patch.object(service, "_record_gap", new=AsyncMock()):
        await service.ask(query="anything", vertical="grain", participant_safe=False)

    assert search.await_args.kwargs["filters"] == {}


@pytest.mark.asyncio
async def test_a_gap_signal_records_the_filters_actually_applied():
    """A curator seeing 'no matching chunks' must be able to tell why.

    Recording only the caller's filters hides the safety exclusions, which makes
    an exclusion-caused miss look like a hole in the corpus and sends the curator
    off to acquire knowledge that is already there.
    """
    gap = AsyncMock()
    with patch.object(service, "get_embedding", new=AsyncMock(return_value=[0.0] * 1536)), \
         patch.object(service, "search_reference_library", new=AsyncMock(return_value=[])), \
         patch.object(service, "_record_gap", new=gap):
        await service.ask(query="anything", vertical="grain", filters={"topic": "payment_terms"})

    recorded = gap.await_args.args[2]
    assert recorded["topic"] == "payment_terms"
    assert recorded["evidence_class"] == {"not": ["demo_invented"]}
