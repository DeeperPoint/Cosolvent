"""Tests for vector-service filter semantics."""

from __future__ import annotations

from sqlalchemy import column, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.modules.discovery import vector_service


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_metadata_list_filter_uses_overlap_style_conditions():
    stmt = select(1)
    metadata = column("vector_metadata", JSONB)
    stmt = vector_service._apply_metadata_filters(stmt, metadata, {"skills": ["Python", "Go"]})
    rendered = _sql(stmt)
    assert "@>" in rendered
    assert " OR " in rendered


def test_metadata_empty_list_filter_returns_false_predicate():
    stmt = select(1)
    metadata = column("vector_metadata", JSONB)
    stmt = vector_service._apply_metadata_filters(stmt, metadata, {"skills": []})
    rendered = _sql(stmt)
    assert "false" in rendered.lower()


def test_profile_field_filter_supports_scalar_or_array_match():
    stmt = select(1)
    profile_data = column("data", JSONB)
    stmt = vector_service._apply_profile_field_filters(stmt, profile_data, {"country": "Canada"})
    rendered = _sql(stmt)
    assert "@>" in rendered
    assert " OR " in rendered
