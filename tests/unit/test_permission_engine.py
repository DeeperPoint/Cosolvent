"""Tests for the permission engine."""

from pathlib import Path

from app.core.marketplace_config import load_marketplace_config
from app.engine.permission_engine import (
    can_initiate_conversation,
    check_permission,
    has_completed_required_onboarding,
    get_allowed_conversation_targets,
    requires_onboarding,
)

FIXTURES = Path(__file__).parent.parent / "test_config"


def _agri():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


def _talent():
    return load_marketplace_config(FIXTURES / "talent.yaml")


class TestCheckPermission:
    def test_producer_can_list(self):
        assert check_permission(_agri(), "producer", "can_list") is True

    def test_producer_cannot_search(self):
        assert check_permission(_agri(), "producer", "can_search") is False

    def test_buyer_can_search(self):
        assert check_permission(_agri(), "buyer", "can_search") is True

    def test_unknown_type(self):
        assert check_permission(_agri(), "nonexistent", "can_search") is False

    def test_unknown_permission(self):
        assert check_permission(_agri(), "buyer", "nonexistent_perm") is False


class TestCanInitiateConversation:
    def test_buyer_to_producer(self):
        allowed, requires_approval = can_initiate_conversation(_agri(), "buyer", "producer")
        assert allowed is True
        assert requires_approval is True

    def test_producer_to_buyer_not_allowed(self):
        allowed, _ = can_initiate_conversation(_agri(), "producer", "buyer")
        assert allowed is False

    def test_talent_multi_rules(self):
        cfg = _talent()
        allowed, approval = can_initiate_conversation(cfg, "employer", "candidate")
        assert allowed is True
        assert approval is True

        allowed, approval = can_initiate_conversation(cfg, "recruiter", "employer")
        assert allowed is True
        assert approval is False


class TestGetAllowedTargets:
    def test_buyer_targets(self):
        targets = get_allowed_conversation_targets(_agri(), "buyer")
        assert targets == ["producer"]

    def test_producer_no_targets(self):
        targets = get_allowed_conversation_targets(_agri(), "producer")
        assert targets == []

    def test_recruiter_targets(self):
        targets = get_allowed_conversation_targets(_talent(), "recruiter")
        assert set(targets) == {"candidate", "employer"}


class TestOnboardingGuards:
    def test_requires_onboarding_flag_reads_from_type_permissions(self):
        assert requires_onboarding(_agri(), "producer") is True
        assert requires_onboarding(_agri(), "nonexistent") is False

    def test_admin_is_always_considered_onboarded(self):
        assert has_completed_required_onboarding(
            _agri(),
            {"role": "admin", "participant_type": None, "has_onboarded": False},
        )

    def test_user_must_have_has_onboarded_when_type_requires_it(self):
        cfg = _agri()
        assert not has_completed_required_onboarding(
            cfg,
            {"role": "user", "participant_type": "producer", "has_onboarded": False},
        )
        assert has_completed_required_onboarding(
            cfg,
            {"role": "user", "participant_type": "producer", "has_onboarded": True},
        )
