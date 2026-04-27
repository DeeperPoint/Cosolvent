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
class ThemeDef:
    """Per-marketplace UI theme.

    Tokens flow into ``tailwind.config.ts`` and ``globals.css`` so every page
    picks up the marketplace's voice automatically.
    """

    primary: str = "#2563eb"        # CSS color, applied as --primary
    accent: str = "#4f46e5"         # CSS color, applied as --accent
    neutral: str = "neutral"        # warm | cool | neutral
    font: str = "Inter"             # Google Font family
    radius: str = "md"              # sm | md | lg | xl
    logo_emoji: str = ""            # tiny mark shown beside the marketplace name
    voice: str = ""                 # one-sentence brand voice for agent fill


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
    theme: ThemeDef = field(default_factory=ThemeDef)


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

    theme = _parse_theme(raw.get("theme", {}), industry=industry, marketplace_name=name)

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
        theme=theme,
    )


# ── Theme defaults ────────────────────────────────────────────────────

# Industry-derived theme presets. Picked when the user hasn't declared a
# ``theme:`` block. Everything is overrideable per-token.
_INDUSTRY_THEME_PRESETS: dict[str, dict[str, str]] = {
    "agriculture": {
        "primary": "#7c5e2a",
        "accent": "#5a8a4a",
        "neutral": "warm",
        "font": "Plus Jakarta Sans",
        "radius": "lg",
        "logo_emoji": "🌾",
        "voice": "grounded and practical, agricultural professionals talking shop",
    },
    "talent": {
        "primary": "#2563eb",
        "accent": "#7c3aed",
        "neutral": "cool",
        "font": "Inter",
        "radius": "md",
        "logo_emoji": "✦",
        "voice": "confident and modern, professional services tone",
    },
    "healthcare": {
        "primary": "#0891b2",
        "accent": "#14b8a6",
        "neutral": "warm",
        "font": "Source Sans 3",
        "radius": "md",
        "logo_emoji": "✚",
        "voice": "calm, careful, patient-respectful",
    },
    "finance": {
        "primary": "#0f172a",
        "accent": "#0891b2",
        "neutral": "cool",
        "font": "Inter",
        "radius": "sm",
        "logo_emoji": "◆",
        "voice": "precise, conservative, numbers-forward",
    },
    "education": {
        "primary": "#7c3aed",
        "accent": "#f59e0b",
        "neutral": "warm",
        "font": "Plus Jakarta Sans",
        "radius": "lg",
        "logo_emoji": "✎",
        "voice": "encouraging and clear, teacher-to-learner",
    },
    "logistics": {
        "primary": "#ea580c",
        "accent": "#0891b2",
        "neutral": "neutral",
        "font": "Inter",
        "radius": "sm",
        "logo_emoji": "▣",
        "voice": "operational and direct, no fluff",
    },
}

_DEFAULT_THEME = {
    "primary": "#2563eb",
    "accent": "#4f46e5",
    "neutral": "neutral",
    "font": "Inter",
    "radius": "md",
    "logo_emoji": "◎",
    "voice": "clear, professional marketplace voice",
}


def _parse_theme(raw: dict[str, Any], *, industry: str, marketplace_name: str) -> ThemeDef:
    """Resolve theme tokens with this priority: explicit YAML → industry preset → default."""
    preset = _INDUSTRY_THEME_PRESETS.get(_normalize_industry(industry), _DEFAULT_THEME)
    base = {**_DEFAULT_THEME, **preset, **{k: v for k, v in raw.items() if v is not None}}
    return ThemeDef(
        primary=str(base["primary"]),
        accent=str(base["accent"]),
        neutral=str(base["neutral"]),
        font=str(base["font"]),
        radius=str(base["radius"]),
        logo_emoji=str(base["logo_emoji"]),
        voice=str(base["voice"]),
    )


def _normalize_industry(industry: str) -> str:
    """Map a free-form industry string to a known preset key."""
    s = (industry or "").lower()
    for key in _INDUSTRY_THEME_PRESETS:
        if key in s:
            return key
    return ""
