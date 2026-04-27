"""Parse marketplace.yaml into raw frontend-oriented structures.

Uses the standalone ``yaml_config`` loader so the frontend compiler has
zero dependency on the backend Python package.
"""

from __future__ import annotations

from dataclasses import dataclass

from .yaml_config import MarketplaceYaml, ThemeDef


@dataclass(frozen=True)
class RawFieldDef:
    name: str
    label: str
    field_type: str
    required: bool
    options: tuple[str, ...]
    visibility: str
    searchable: bool


@dataclass(frozen=True)
class RawSection:
    name: str
    fields: tuple[RawFieldDef, ...]


@dataclass(frozen=True)
class RawPermissions:
    can_list: bool
    can_search: bool
    can_initiate_conversation: bool
    can_receive_conversation: bool
    can_share_private_assets: bool
    requires_onboarding: bool
    requires_approval: bool
    visible_in_search: bool


@dataclass(frozen=True)
class RawOnboarding:
    requires_approval: bool
    approval_type: str
    document_upload_required: bool
    ai_extraction_enabled: bool
    ai_profile_generation: bool
    profile_completeness_threshold: int


@dataclass(frozen=True)
class RawEntity:
    slug: str
    name: str
    role: str
    sections: tuple[RawSection, ...]
    permissions: RawPermissions
    onboarding: RawOnboarding


@dataclass(frozen=True)
class RawConversationRule:
    initiator: str
    receiver: str
    requires_approval: bool


@dataclass(frozen=True)
class RawMarketplace:
    name: str
    description: str
    industry: str
    entities: tuple[RawEntity, ...]
    conversation_rules: tuple[RawConversationRule, ...]
    searchable_types: tuple[str, ...]
    filter_fields: tuple[str, ...]
    anonymous_search_enabled: bool
    allow_public_signup: bool
    allow_public_application: bool
    theme: ThemeDef = ThemeDef()


def parse_marketplace(config: MarketplaceYaml) -> RawMarketplace:
    """Convert a parsed MarketplaceYaml into raw frontend structures."""
    entities: list[RawEntity] = []

    for pt in config.participants:
        sections: list[RawSection] = []
        for section in pt.sections:
            fields = tuple(
                RawFieldDef(
                    name=f.name,
                    label=f.label,
                    field_type=f.type,
                    required=f.required,
                    options=f.options,
                    visibility=f.visibility,
                    searchable=f.searchable,
                )
                for f in section.fields
            )
            sections.append(RawSection(name=section.name, fields=fields))

        perms = pt.permissions
        entities.append(
            RawEntity(
                slug=pt.slug,
                name=pt.name,
                role=pt.role,
                sections=tuple(sections),
                permissions=RawPermissions(
                    can_list=perms.can_list,
                    can_search=perms.can_search,
                    can_initiate_conversation=perms.can_initiate_conversation,
                    can_receive_conversation=perms.can_receive_conversation,
                    can_share_private_assets=perms.can_share_private_assets,
                    requires_onboarding=perms.requires_onboarding,
                    requires_approval=perms.requires_approval,
                    visible_in_search=perms.visible_in_search,
                ),
                onboarding=RawOnboarding(
                    requires_approval=pt.onboarding.requires_approval,
                    approval_type=pt.onboarding.approval_type,
                    document_upload_required=pt.onboarding.document_upload_required,
                    ai_extraction_enabled=pt.onboarding.ai_extraction_enabled,
                    ai_profile_generation=pt.onboarding.ai_profile_generation,
                    profile_completeness_threshold=pt.onboarding.profile_completeness_threshold,
                ),
            )
        )

    conversation_rules = tuple(
        RawConversationRule(
            initiator=r.initiator,
            receiver=r.receiver,
            requires_approval=r.requires_approval,
        )
        for r in config.conversation_rules
    )

    return RawMarketplace(
        name=config.name,
        description=config.description,
        industry=config.industry,
        entities=tuple(entities),
        conversation_rules=conversation_rules,
        searchable_types=config.searchable_types,
        filter_fields=config.filter_fields,
        anonymous_search_enabled=config.anonymous_search_enabled,
        allow_public_signup=config.allow_public_signup,
        allow_public_application=config.allow_public_application,
        theme=config.theme,
    )
