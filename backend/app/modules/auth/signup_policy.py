"""Whether self-service signup / public application intake is allowed (YAML + env override)."""

from __future__ import annotations

from app.core.config import settings
from app.core.marketplace_config import MarketplaceConfig


def public_signup_allowed(config: MarketplaceConfig) -> bool:
    if settings.allow_public_signup is not None:
        return settings.allow_public_signup
    return config.auth.allow_public_signup


def public_application_allowed(config: MarketplaceConfig) -> bool:
    """Anonymous profile application (POST .../register with email+fields, no account)."""
    if settings.allow_public_application is not None:
        return settings.allow_public_application
    return config.auth.allow_public_application
