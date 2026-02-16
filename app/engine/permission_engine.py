"""Permission checks driven by marketplace config."""

from __future__ import annotations

from typing import Any

from app.core.marketplace_config import MarketplaceConfig


def check_permission(config: MarketplaceConfig, type_slug: str, permission: str) -> bool:
    """Check if a participant type has a specific permission."""
    pt = config.get_type(type_slug)
    if pt is None:
        return False
    return getattr(pt.permissions, permission, False)


def can_initiate_conversation(
    config: MarketplaceConfig,
    initiator_type: str,
    receiver_type: str,
) -> tuple[bool, bool]:
    """Check if initiator can start a conversation with receiver.

    Returns (allowed, requires_approval).
    """
    for rule in config.communication.conversation_rules:
        if rule.initiator == initiator_type and rule.receiver == receiver_type:
            return True, rule.requires_approval
    return False, False


def get_allowed_conversation_targets(
    config: MarketplaceConfig, initiator_type: str
) -> list[str]:
    """Return list of type slugs that the given type can initiate conversations with."""
    return [
        rule.receiver
        for rule in config.communication.conversation_rules
        if rule.initiator == initiator_type
    ]


def requires_onboarding(config: MarketplaceConfig, type_slug: str) -> bool:
    """Return whether the participant type is required to onboard."""
    pt = config.get_type(type_slug)
    if pt is None:
        return False
    return bool(pt.permissions.requires_onboarding)


def has_completed_required_onboarding(
    config: MarketplaceConfig,
    user: dict[str, Any],
) -> bool:
    """Return True when the user has satisfied onboarding requirements."""
    if user.get("role") == "admin":
        return True

    participant_type = str(user.get("participant_type", ""))
    if not requires_onboarding(config, participant_type):
        return True
    return bool(user.get("has_onboarded", False))
