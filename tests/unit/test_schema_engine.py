"""Tests for the dynamic schema engine."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.marketplace_config import load_marketplace_config
from app.engine.schema_engine import clear_cache, get_profile_model, validate_profile_fields

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
