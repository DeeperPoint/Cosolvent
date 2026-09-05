"""Visibility-based field filtering for profiles.

Three field-visibility levels:
  - public:    visible to everyone (including anonymous)
  - protected: visible to authenticated users
  - private:   visible only to profile owner and admins

Four viewer tiers. ``sealed`` is not a fourth field-visibility level — it is a
viewer tier that is deliberately held to the ``anonymous`` allowance despite the
viewer being authenticated. It exists for the confidential-matching disclosure
protocol (GAP-6/13): two parties who are counterparties on a deal whose
disclosure level has not yet advanced to "revealed" must not see each other's
``protected`` fields, even though both are ordinary authenticated marketplace
users who would see ``protected`` fields on *any other* profile. Callers that
have no deal context (e.g. discovery search, an unrelated stranger's profile)
never need it and pass ``authenticated`` as before — only a caller that knows
about a specific viewer/owner deal relationship (see
``app.modules.deals.service.is_sealed_from``) downgrades to ``sealed``.
"""

from __future__ import annotations

from typing import Any, Literal

from app.core.marketplace_config import MarketplaceConfig, ProfileSchema

ViewerTier = Literal["anonymous", "authenticated", "sealed", "owner"]


def filter_fields(
    schema: ProfileSchema,
    fields: dict[str, Any],
    viewer_tier: ViewerTier,
) -> dict[str, Any]:
    """Return a copy of fields filtered by the viewer's visibility tier."""
    allowed_vis = _allowed_visibilities(viewer_tier)
    field_vis = {f.name: f.visibility for f in schema.all_fields}

    return {k: v for k, v in fields.items() if field_vis.get(k, "private") in allowed_vis}


def filter_fields_for_discovery(
    config: MarketplaceConfig,
    schema: ProfileSchema,
    fields: dict[str, Any],
    viewer_tier: ViewerTier,
) -> dict[str, Any]:
    """Return a copy of fields filtered by discovery visibility policy from config."""
    allowed_vis = _allowed_discovery_visibilities(config, viewer_tier)
    field_vis = {f.name: f.visibility for f in schema.all_fields}
    return {k: v for k, v in fields.items() if field_vis.get(k, "private") in allowed_vis}


def get_viewer_tier(
    *,
    is_authenticated: bool,
    is_owner: bool,
    is_admin: bool,
) -> ViewerTier:
    """Determine the viewer tier based on auth/ownership/admin status."""
    if is_owner or is_admin:
        return "owner"
    if is_authenticated:
        return "authenticated"
    return "anonymous"


def _allowed_visibilities(tier: ViewerTier) -> set[str]:
    if tier == "owner":
        return {"public", "protected", "private"}
    if tier == "authenticated":
        return {"public", "protected"}
    # "sealed" falls through to the same allowance as "anonymous" on purpose —
    # see the module docstring.
    return {"public"}


def _allowed_discovery_visibilities(config: MarketplaceConfig, tier: ViewerTier) -> set[str]:
    if tier == "owner":
        return {"public", "protected", "private"}
    if tier == "authenticated":
        max_visibility = config.discovery.result_visibility.authenticated
    else:
        max_visibility = config.discovery.result_visibility.anonymous
    if max_visibility == "protected":
        return {"public", "protected"}
    return {"public"}
