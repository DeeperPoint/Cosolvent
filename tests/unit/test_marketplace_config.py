"""Tests for marketplace YAML config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.marketplace_config import MarketplaceConfig, load_marketplace_config

FIXTURES = Path(__file__).parent.parent / "test_config"


class TestLoadValidConfigs:
    def test_agriculture_config(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        assert cfg.marketplace.name == "GrainPlaza"
        assert len(cfg.participant_types) == 2
        assert cfg.get_type("producer") is not None
        assert cfg.get_type("buyer") is not None

    def test_talent_config(self):
        cfg = load_marketplace_config(FIXTURES / "talent.yaml")
        assert cfg.marketplace.name == "TalentBridge"
        assert len(cfg.participant_types) == 3
        assert cfg.get_type("recruiter") is not None

    def test_minimal_config(self):
        cfg = load_marketplace_config(FIXTURES / "minimal.yaml")
        assert cfg.marketplace.name == "MinimalMarket"
        assert len(cfg.participant_types) == 2


class TestParticipantTypes:
    def test_type_slugs(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        assert set(cfg.type_slugs()) == {"producer", "buyer"}

    def test_permissions(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        producer = cfg.get_type("producer")
        assert producer.permissions.can_list is True
        assert producer.permissions.can_search is False
        buyer = cfg.get_type("buyer")
        assert buyer.permissions.can_search is True
        assert buyer.permissions.can_initiate_conversation is True


class TestProfileSchemas:
    def test_all_fields(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        schema = cfg.profile_schemas["producer"]
        names = [f.name for f in schema.all_fields]
        assert "farm_name" in names
        assert "financial_notes" in names

    def test_get_field(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        schema = cfg.profile_schemas["producer"]
        field = schema.get_field("country")
        assert field is not None
        assert field.type == "select"
        assert "Canada" in field.options

    def test_visibility_tiers(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        schema = cfg.profile_schemas["producer"]
        field_vis = {f.name: f.visibility for f in schema.all_fields}
        assert field_vis["farm_name"] == "public"
        assert field_vis["annual_production"] == "protected"
        assert field_vis["financial_notes"] == "private"


class TestOnboarding:
    def test_producer_onboarding(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        ob = cfg.onboarding["producer"]
        assert ob.requires_approval is True
        assert ob.approval_type == "manual"
        assert ob.ai_extraction_enabled is True

    def test_buyer_onboarding(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        ob = cfg.onboarding["buyer"]
        assert ob.requires_approval is False
        assert ob.approval_type == "auto"


class TestCommunicationRules:
    def test_rules_loaded(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        rules = cfg.communication.conversation_rules
        assert len(rules) == 1
        assert rules[0].initiator == "buyer"
        assert rules[0].receiver == "producer"

    def test_multi_rules(self):
        cfg = load_marketplace_config(FIXTURES / "talent.yaml")
        rules = cfg.communication.conversation_rules
        assert len(rules) == 3


class TestDiscovery:
    def test_searchable_types(self):
        cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
        assert cfg.discovery.searchable_types == ["producer"]
        assert cfg.discovery.access.anonymous_search_enabled is False
        assert cfg.discovery.access.anonymous_filter_mode == "public_only"

    def test_ai_settings(self):
        cfg = load_marketplace_config(FIXTURES / "minimal.yaml")
        assert cfg.discovery.ai.vector_search_enabled is False
        assert cfg.discovery.ai.profile_retrieval_mode == "hybrid"
        assert cfg.discovery.ai.rag_failure_behavior == "service_unavailable"


class TestCrossValidation:
    def _make_raw(self, **overrides):
        """Return a valid raw config dict that can be tweaked for negative tests."""
        base = yaml.safe_load((FIXTURES / "agriculture.yaml").read_text())
        base.update(overrides)
        return base

    def test_too_few_types(self):
        raw = self._make_raw()
        raw["participant_types"] = raw["participant_types"][:1]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_too_many_types(self):
        raw = self._make_raw()
        raw["participant_types"] = raw["participant_types"] * 3  # 6 types
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_missing_profile_schema(self):
        raw = self._make_raw()
        del raw["profile_schemas"]["producer"]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_missing_onboarding(self):
        raw = self._make_raw()
        del raw["onboarding"]["producer"]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_bad_conversation_rule(self):
        raw = self._make_raw()
        raw["communication"]["conversation_rules"] = [
            {"initiator": "nonexistent", "receiver": "producer"}
        ]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_no_searchable_type(self):
        raw = self._make_raw()
        for pt in raw["participant_types"]:
            pt["permissions"]["can_search"] = False
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_no_visible_type(self):
        raw = self._make_raw()
        for pt in raw["participant_types"]:
            pt["permissions"]["visible_in_search"] = False
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_bad_discovery_searchable_type(self):
        raw = self._make_raw()
        raw["discovery"]["searchable_types"] = ["nonexistent"]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_bad_filter_field(self):
        raw = self._make_raw()
        raw["discovery"]["filter_fields"] = ["nonexistent_field"]
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_searchable_type_must_be_visible(self):
        raw = self._make_raw()
        for pt in raw["participant_types"]:
            if pt["slug"] == "producer":
                pt["permissions"]["visible_in_search"] = False
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_invalid_similarity_threshold(self):
        raw = self._make_raw()
        raw["discovery"]["ai"]["profile_similarity_threshold"] = 1.2
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_select_field_without_options(self):
        raw = self._make_raw()
        raw["profile_schemas"]["producer"]["sections"][0]["fields"][1]["options"] = None
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_duplicate_participant_slug_is_rejected(self):
        raw = self._make_raw()
        primary_slug = raw["participant_types"][0]["slug"]
        secondary_slug = raw["participant_types"][1]["slug"]

        raw["participant_types"][1]["slug"] = primary_slug
        raw["profile_schemas"].pop(secondary_slug)
        raw["onboarding"].pop(secondary_slug)
        raw["communication"]["conversation_rules"] = [
            {"initiator": primary_slug, "receiver": primary_slug, "requires_approval": True}
        ]
        raw["discovery"]["searchable_types"] = [primary_slug]

        with pytest.raises(Exception, match="Duplicate participant slug"):
            MarketplaceConfig(**raw)

    def test_invalid_slug_pattern_is_rejected(self):
        raw = self._make_raw()
        old_slug = raw["participant_types"][0]["slug"]
        bad_slug = "Bad-Slug"

        raw["participant_types"][0]["slug"] = bad_slug
        raw["profile_schemas"][bad_slug] = raw["profile_schemas"].pop(old_slug)
        raw["onboarding"][bad_slug] = raw["onboarding"].pop(old_slug)
        raw["discovery"]["searchable_types"] = [
            bad_slug if slug == old_slug else slug
            for slug in raw["discovery"]["searchable_types"]
        ]
        for rule in raw["communication"]["conversation_rules"]:
            if rule["initiator"] == old_slug:
                rule["initiator"] = bad_slug
            if rule["receiver"] == old_slug:
                rule["receiver"] = bad_slug

        with pytest.raises(Exception, match="Invalid participant slug"):
            MarketplaceConfig(**raw)

    def test_reserved_slug_is_rejected(self):
        raw = self._make_raw()
        old_slug = raw["participant_types"][0]["slug"]
        reserved_slug = "admin"

        raw["participant_types"][0]["slug"] = reserved_slug
        raw["profile_schemas"][reserved_slug] = raw["profile_schemas"].pop(old_slug)
        raw["onboarding"][reserved_slug] = raw["onboarding"].pop(old_slug)
        raw["discovery"]["searchable_types"] = [
            reserved_slug if slug == old_slug else slug
            for slug in raw["discovery"]["searchable_types"]
        ]
        for rule in raw["communication"]["conversation_rules"]:
            if rule["initiator"] == old_slug:
                rule["initiator"] = reserved_slug
            if rule["receiver"] == old_slug:
                rule["receiver"] = reserved_slug

        with pytest.raises(Exception, match="is reserved"):
            MarketplaceConfig(**raw)

    def test_unknown_nested_field_is_rejected(self):
        raw = self._make_raw()
        raw["onboarding"]["producer"]["new_flag"] = True
        with pytest.raises(Exception):
            MarketplaceConfig(**raw)

    def test_onboarding_threshold_must_be_between_zero_and_hundred(self):
        raw = self._make_raw()
        raw["onboarding"]["producer"]["profile_completeness_threshold"] = 101
        with pytest.raises(Exception, match="between 0 and 100"):
            MarketplaceConfig(**raw)

        raw = self._make_raw()
        raw["onboarding"]["producer"]["profile_completeness_threshold"] = -1
        with pytest.raises(Exception, match="between 0 and 100"):
            MarketplaceConfig(**raw)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_marketplace_config("/nonexistent/path.yaml")
