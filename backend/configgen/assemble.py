"""Assemble a MarketDefinition into a marketplace.yaml config dict.

Pure/deterministic. The output dict is intended to be handed to ``validate.py``, which
runs it through Cosolvent's real ``MarketplaceConfig`` model (the acceptance oracle).
"""

from __future__ import annotations

from typing import Any

from .ir import FieldDef, MarketDefinition
from .permissions import (
    conversation_rules,
    discovery_block,
    onboarding_for,
    permissions_for,
)


def _field_dict(f: FieldDef) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": f.name,
        "label": f.label,
        "type": f.type,
        "required": f.required,
        "visibility": f.visibility,
        "searchable": f.searchable,
    }
    if f.type in ("select", "multi_select"):
        d["options"] = list(f.options or [])
    if f.type == "files" and f.accepted_types:
        d["accepted_types"] = list(f.accepted_types)
    return d


def assemble(market: MarketDefinition) -> dict[str, Any]:
    participant_types = []
    profile_schemas: dict[str, Any] = {}
    onboarding: dict[str, Any] = {}

    for p in market.participants:
        participant_types.append(
            {"name": p.name, "slug": p.slug, "role": p.role, "permissions": permissions_for(p.role)}
        )
        profile_schemas[p.slug] = {
            "sections": [
                {"name": s.name, "fields": [_field_dict(f) for f in s.fields]} for s in p.sections
            ]
        }
        onboarding[p.slug] = onboarding_for(p.role)

    return {
        "marketplace": {
            "name": market.name,
            "description": market.description,
            "industry": market.industry,
        },
        "auth": {"allow_public_signup": False, "allow_public_application": True},
        "participant_types": participant_types,
        "profile_schemas": profile_schemas,
        "onboarding": onboarding,
        "communication": {"conversation_rules": conversation_rules(market.participants)},
        "discovery": discovery_block(market),
        "ai": {"enabled_providers": ["openai"]},
    }
