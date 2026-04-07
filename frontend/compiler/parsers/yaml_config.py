"""Standalone marketplace.yaml loader for the frontend compiler.

This module reads marketplace.yaml directly using pyyaml, extracting only
the fields the frontend compiler needs. It does NOT depend on the backend's
Pydantic ``MarketplaceConfig`` model, keeping the frontend compiler fully
self-contained.

Validation is intentionally lightweight — the backend compiler is expected
to have validated the YAML before the frontend compiler runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    type: str
    required: bool = False
    options: tuple[str, ...] = ()
    visibility: str = "public"
    searchable: bool = False


@dataclass(frozen=True)
class SectionDef:
    name: str
    fields: tuple[FieldDef, ...]


@dataclass(frozen=True)
class PermissionsDef:
    can_list: bool = False
    can_search: bool = False
    can_initiate_conversation: bool = False
    can_receive_conversation: bool = False
    can_share_private_assets: bool = False
    requires_onboarding: bool = True
    requires_approval: bool = False
    visible_in_search: bool = False


@dataclass(frozen=True)
class OnboardingDef:
    requires_approval: bool = True
    approval_type: str = "manual"
    document_upload_required: bool = False
    ai_extraction_enabled: bool = False
    ai_profile_generation: bool = False
    profile_completeness_threshold: int = 100


@dataclass(frozen=True)
class ParticipantDef:
    slug: str
    name: str
    role: str
    sections: tuple[SectionDef, ...]
    permissions: PermissionsDef
    onboarding: OnboardingDef


@dataclass(frozen=True)
class ConversationRuleDef:
    initiator: str
    receiver: str
    requires_approval: bool = True


@dataclass(frozen=True)
class MarketplaceYaml:
    """Lightweight representation of marketplace.yaml for frontend generation."""

    name: str
    description: str
    industry: str
    participants: tuple[ParticipantDef, ...]
    conversation_rules: tuple[ConversationRuleDef, ...]
    searchable_types: tuple[str, ...]
    filter_fields: tuple[str, ...]
    anonymous_search_enabled: bool = False
    allow_public_signup: bool = True
    allow_public_application: bool = True


def load_marketplace_yaml(path: str | Path) -> MarketplaceYaml:
    """Load and parse a marketplace.yaml file into ``MarketplaceYaml``."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Marketplace config not found: {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _parse_raw(raw)


def parse_marketplace_dict(raw: dict[str, Any]) -> MarketplaceYaml:
    """Parse an already-loaded dict (useful for tests)."""
    return _parse_raw(raw)


def _parse_raw(raw: dict[str, Any]) -> MarketplaceYaml:
    mkt = raw.get("marketplace", {})
    name = mkt.get("name", "Marketplace")
    description = mkt.get("description", "")
    industry = mkt.get("industry", "")

    pt_list = raw.get("participant_types", [])
    schemas = raw.get("profile_schemas", {})
    onboarding_map = raw.get("onboarding", {})

    participants: list[ParticipantDef] = []
    for pt in pt_list:
        slug = pt["slug"]
        perms_raw = pt.get("permissions", {})
        perms = PermissionsDef(
            can_list=perms_raw.get("can_list", False),
            can_search=perms_raw.get("can_search", False),
            can_initiate_conversation=perms_raw.get("can_initiate_conversation", False),
            can_receive_conversation=perms_raw.get("can_receive_conversation", False),
            can_share_private_assets=perms_raw.get("can_share_private_assets", False),
            requires_onboarding=perms_raw.get("requires_onboarding", True),
            requires_approval=perms_raw.get("requires_approval", False),
            visible_in_search=perms_raw.get("visible_in_search", False),
        )

        ob_raw = onboarding_map.get(slug, {})
        onboarding = OnboardingDef(
            requires_approval=ob_raw.get("requires_approval", True),
            approval_type=ob_raw.get("approval_type", "manual"),
            document_upload_required=ob_raw.get("document_upload_required", False),
            ai_extraction_enabled=ob_raw.get("ai_extraction_enabled", False),
            ai_profile_generation=ob_raw.get("ai_profile_generation", False),
            profile_completeness_threshold=ob_raw.get("profile_completeness_threshold", 100),
        )

        schema_raw = schemas.get(slug, {})
        sections: list[SectionDef] = []
        for sec in schema_raw.get("sections", []):
            fields = tuple(
                FieldDef(
                    name=f["name"],
                    label=f.get("label", f["name"]),
                    type=f.get("type", "text"),
                    required=f.get("required", False),
                    options=tuple(f["options"]) if f.get("options") else (),
                    visibility=f.get("visibility", "public"),
                    searchable=f.get("searchable", False),
                )
                for f in sec.get("fields", [])
            )
            sections.append(SectionDef(name=sec["name"], fields=fields))

        participants.append(
            ParticipantDef(
                slug=slug,
                name=pt["name"],
                role=pt.get("role", "supply"),
                sections=tuple(sections),
                permissions=perms,
                onboarding=onboarding,
            )
        )

    comm = raw.get("communication", {})
    rules = tuple(
        ConversationRuleDef(
            initiator=r["initiator"],
            receiver=r["receiver"],
            requires_approval=r.get("requires_approval", True),
        )
        for r in comm.get("conversation_rules", [])
    )

    disc = raw.get("discovery", {})
    access = disc.get("access", {})
    auth = raw.get("auth", {})

    return MarketplaceYaml(
        name=name,
        description=description,
        industry=industry,
        participants=tuple(participants),
        conversation_rules=rules,
        searchable_types=tuple(disc.get("searchable_types", [])),
        filter_fields=tuple(disc.get("filter_fields", [])),
        anonymous_search_enabled=access.get("anonymous_search_enabled", False),
        allow_public_signup=auth.get("allow_public_signup", True),
        allow_public_application=auth.get("allow_public_application", True),
    )
