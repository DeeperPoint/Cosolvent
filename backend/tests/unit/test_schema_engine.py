"""Tests for the dynamic schema engine."""

from pathlib import Path

import pytest
from pydantic import ValidationError, create_model

from app.core.marketplace_config import FieldDefinition, load_marketplace_config
from app.engine.schema_engine import _python_type, clear_cache, get_profile_model, validate_profile_fields

FIXTURES = Path(__file__).parent.parent / "test_config"


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def config():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


class TestBuildModel:
    def test_producer_model_created(self, config):
        model = get_profile_model(config, "producer")
        assert model.__name__ == "ProducerProfile"

    def test_required_fields(self, config):
        model = get_profile_model(config, "producer")
        fields = model.model_fields
        assert fields["farm_name"].is_required()
        assert fields["country"].is_required()
        assert not fields["description"].is_required()

    def test_invalid_type_slug(self, config):
        with pytest.raises(ValueError, match="No profile schema"):
            get_profile_model(config, "nonexistent")


class TestValidateFields:
    def test_valid_producer(self, config):
        data = {
            "farm_name": "Valley Farms",
            "country": "Canada",
            "primary_crops": ["Wheat", "Barley"],
        }
        result = validate_profile_fields(config, "producer", data)
        assert result["farm_name"] == "Valley Farms"
        # Optional fields not provided are excluded from output
        assert "description" not in result or result["description"] is None

    def test_missing_required(self, config):
        with pytest.raises(ValidationError):
            validate_profile_fields(config, "producer", {"country": "Canada"})

    def test_wrong_type(self, config):
        with pytest.raises(ValidationError):
            validate_profile_fields(config, "producer", {
                "farm_name": "Test",
                "country": "Canada",
                "primary_crops": "not a list",
            })

    def test_buyer_validation(self, config):
        result = validate_profile_fields(config, "buyer", {"org_name": "ACME Corp"})
        assert result["org_name"] == "ACME Corp"


class TestTalentConfig:
    def test_three_type_models(self):
        cfg = load_marketplace_config(FIXTURES / "talent.yaml")
        for slug in ["candidate", "employer", "recruiter"]:
            model = get_profile_model(cfg, slug)
            assert model is not None


class TestDateRangeField:
    """date_range: [start, end] ISO dates, the input shape GAP-18's window_overlap
    comparator expects. Added because no existing field type produces a plain list
    without requiring `options` (select/multi_select do) -- a readiness/availability
    window has no fixed option set."""

    def test_python_type_is_list(self):
        field = FieldDefinition(name="readiness_window", label="Readiness window", type="date_range")
        assert _python_type(field) == list[str]

    def test_accepts_two_element_list(self):
        py_type = _python_type(FieldDefinition(name="readiness_window", label="x", type="date_range"))
        model = create_model("T", readiness_window=(py_type, ...))
        instance = model(readiness_window=["2027-05-01", "2027-07-01"])
        assert instance.readiness_window == ["2027-05-01", "2027-07-01"]

    def test_rejects_plain_string(self):
        py_type = _python_type(FieldDefinition(name="readiness_window", label="x", type="date_range"))
        model = create_model("T", readiness_window=(py_type, ...))
        with pytest.raises(ValidationError):
            model(readiness_window="2027-05-01")
