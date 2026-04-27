"""Frontend compiler intermediate representation.

All IR types are frozen dataclasses to enforce immutability through the
compiler pipeline.  Tuples are used instead of lists so frozen hashing works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldType = Literal[
    "text",
    "number",
    "select",
    "multi_select",
    "date",
    "file",
    "files",
    "rich_text",
    "location",
]

ComponentType = Literal[
    "TextInput",
    "NumberInput",
    "Select",
    "MultiSelect",
    "DatePicker",
    "FileUpload",
    "MultiFileUpload",
    "RichTextEditor",
    "LocationPicker",
]

Visibility = Literal["public", "protected", "private"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE"]
PageKind = Literal["list", "detail", "form", "dashboard", "search", "conversation"]
LayoutKind = Literal["auth", "dashboard", "admin", "public"]


FIELD_TYPE_TO_COMPONENT: dict[FieldType, ComponentType] = {
    "text": "TextInput",
    "number": "NumberInput",
    "select": "Select",
    "multi_select": "MultiSelect",
    "date": "DatePicker",
    "file": "FileUpload",
    "files": "MultiFileUpload",
    "rich_text": "RichTextEditor",
    "location": "LocationPicker",
}

FIELD_TYPE_TO_TS: dict[FieldType, str] = {
    "text": "string",
    "number": "number",
    "select": "string",
    "multi_select": "string[]",
    "date": "string",
    "file": "string",
    "files": "string[]",
    "rich_text": "string",
    "location": "string",
}


# ── Field / Section / Entity ──────────────────────────────────────────


@dataclass(frozen=True)
class FieldIR:
    name: str
    label: str
    field_type: FieldType
    component: ComponentType
    required: bool
    options: tuple[str, ...] = ()
    visibility: Visibility = "public"
    searchable: bool = False
    ts_type: str = "string"


@dataclass(frozen=True)
class SectionIR:
    name: str
    slug: str
    fields: tuple[FieldIR, ...]


@dataclass(frozen=True)
class PermissionsIR:
    can_list: bool
    can_search: bool
    can_initiate_conversation: bool
    can_receive_conversation: bool
    can_share_private_assets: bool
    requires_onboarding: bool
    requires_approval: bool
    visible_in_search: bool


@dataclass(frozen=True)
class OnboardingIR:
    requires_approval: bool
    approval_type: str
    document_upload_required: bool
    ai_extraction_enabled: bool
    ai_profile_generation: bool
    profile_completeness_threshold: int


@dataclass(frozen=True)
class EntityIR:
    slug: str
    name: str
    role: str
    sections: tuple[SectionIR, ...]
    permissions: PermissionsIR
    onboarding: OnboardingIR


# ── Schema / Operation ────────────────────────────────────────────────


@dataclass(frozen=True)
class SchemaPropertyIR:
    name: str
    ts_type: str
    required: bool
    nullable: bool = False


@dataclass(frozen=True)
class SchemaIR:
    name: str
    properties: tuple[SchemaPropertyIR, ...]
    # Free-form schemas (no top-level ``properties``) need their TS shape
    # resolved from the raw ``type`` so we don't emit ``Record<string, unknown>``
    # for what's actually a top-level array (``type: "array"``).
    ts_alias: str | None = None


@dataclass(frozen=True)
class OperationIR:
    id: str
    entity_slug: str | None
    module: str
    kind: str
    method: HttpMethod
    path: str
    request_schema: SchemaIR | None
    response_schema: SchemaIR | None
    auth_required: bool
    path_params: tuple[str, ...] = ()
    query_params: tuple[SchemaPropertyIR, ...] = ()


# ── Pages / Navigation ────────────────────────────────────────────────


@dataclass(frozen=True)
class PageIR:
    id: str
    route: str
    file_path: str
    title: str
    kind: PageKind
    entity_slug: str | None
    operation_ids: tuple[str, ...]
    layout: LayoutKind


@dataclass(frozen=True)
class NavItemIR:
    label: str
    route: str
    icon: str
    roles: tuple[str, ...]
    badge_operation_id: str | None = None


@dataclass(frozen=True)
class NavigationIR:
    items: tuple[NavItemIR, ...]


# ── Top-level config slices ───────────────────────────────────────────


@dataclass(frozen=True)
class AuthIR:
    allow_public_signup: bool
    allow_public_application: bool
    session_cookie_name: str = "session_token"


@dataclass(frozen=True)
class MarketplaceIdentityIR:
    name: str
    description: str
    industry: str


@dataclass(frozen=True)
class ThemeIR:
    """Resolved theme tokens, ready for emission into Tailwind / CSS / prompts."""

    primary: str
    accent: str
    neutral: str       # warm | cool | neutral
    font: str          # Google Font family name
    radius: str        # sm | md | lg | xl
    logo_emoji: str
    voice: str


@dataclass(frozen=True)
class DiscoveryIR:
    searchable_types: tuple[str, ...]
    filter_fields: tuple[str, ...]
    anonymous_search_enabled: bool


# ── Root IR ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FrontendIR:
    marketplace: MarketplaceIdentityIR
    entities: tuple[EntityIR, ...]
    operations: tuple[OperationIR, ...]
    pages: tuple[PageIR, ...]
    navigation: NavigationIR
    auth: AuthIR
    discovery: DiscoveryIR
    schemas: tuple[SchemaIR, ...]
    spec_hash: str
    generator_version: str
    theme: ThemeIR = field(
        default_factory=lambda: ThemeIR(
            primary="#2563eb",
            accent="#4f46e5",
            neutral="neutral",
            font="Inter",
            radius="md",
            logo_emoji="◎",
            voice="clear, professional marketplace voice",
        )
    )
