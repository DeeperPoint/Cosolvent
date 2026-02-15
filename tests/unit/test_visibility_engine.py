"""Tests for the visibility engine."""

from pathlib import Path

from app.core.marketplace_config import load_marketplace_config
from app.engine.visibility_engine import filter_fields, get_viewer_tier

FIXTURES = Path(__file__).parent.parent / "test_config"


def _schema():
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    return cfg.profile_schemas["producer"]


SAMPLE_FIELDS = {
    "farm_name": "Valley Farms",
    "country": "Canada",
    "primary_crops": ["Wheat"],
    "description": "A farm",
    "annual_production": 5000,
    "financial_notes": "Internal only",
}


class TestFilterFields:
    def test_anonymous_sees_public_only(self):
        result = filter_fields(_schema(), SAMPLE_FIELDS, "anonymous")
        assert "farm_name" in result
        assert "country" in result
        assert "annual_production" not in result
        assert "financial_notes" not in result

    def test_authenticated_sees_protected(self):
        result = filter_fields(_schema(), SAMPLE_FIELDS, "authenticated")
        assert "farm_name" in result
        assert "annual_production" in result
        assert "financial_notes" not in result

    def test_owner_sees_all(self):
        result = filter_fields(_schema(), SAMPLE_FIELDS, "owner")
        assert "farm_name" in result
        assert "annual_production" in result
        assert "financial_notes" in result

    def test_missing_fields_not_included(self):
        partial = {"farm_name": "Test"}
        result = filter_fields(_schema(), partial, "owner")
        assert "farm_name" in result
        assert "country" not in result  # not in input


class TestGetViewerTier:
    def test_anonymous(self):
        assert get_viewer_tier(is_authenticated=False, is_owner=False, is_admin=False) == "anonymous"

    def test_authenticated(self):
        assert get_viewer_tier(is_authenticated=True, is_owner=False, is_admin=False) == "authenticated"

    def test_owner(self):
        assert get_viewer_tier(is_authenticated=True, is_owner=True, is_admin=False) == "owner"

    def test_admin(self):
        assert get_viewer_tier(is_authenticated=True, is_owner=False, is_admin=True) == "owner"
