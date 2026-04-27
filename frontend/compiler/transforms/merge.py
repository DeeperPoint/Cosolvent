"""Merge transform — combines parsed OpenAPI + marketplace into a FrontendIR.

This is the central join point of the compiler.  marketplace.yaml drives
*what* entities and UI structure exist; OpenAPI drives *how* the API is
called and what wire shapes look like.
"""

from __future__ import annotations

import hashlib
import json
import re

from ..ir import (
    FIELD_TYPE_TO_COMPONENT,
    FIELD_TYPE_TO_TS,
    AuthIR,
    DiscoveryIR,
    EntityIR,
    FieldIR,
    FieldType,
    FrontendIR,
    MarketplaceIdentityIR,
    ThemeIR,
    OnboardingIR,
    OperationIR,
    PermissionsIR,
    SchemaIR,
    SchemaPropertyIR,
    SectionIR,
)
from ..naming import slug_to_kebab, slug_to_pascal
from ..parsers.marketplace_parser import RawMarketplace
from ..parsers.openapi_parser import RawOpenAPI, RawSchema
from .navigation import derive_navigation
from .page_conventions import derive_pages


def build_frontend_ir(
    openapi: RawOpenAPI,
    marketplace: RawMarketplace,
    *,
    generator_version: str,
) -> FrontendIR:
    """Build the unified FrontendIR from both parsed inputs."""
    spec_hash = _compute_combined_hash(openapi, marketplace)

    entities = tuple(_build_entity(e) for e in marketplace.entities)
    entity_slugs = {e.slug for e in entities}

    schemas = _build_schemas(openapi)
    operations = _build_operations(openapi, entity_slugs, marketplace)

    auth = AuthIR(
        allow_public_signup=marketplace.allow_public_signup,
        allow_public_application=marketplace.allow_public_application,
    )
    discovery = DiscoveryIR(
        searchable_types=marketplace.searchable_types,
        filter_fields=marketplace.filter_fields,
        anonymous_search_enabled=marketplace.anonymous_search_enabled,
    )
    identity = MarketplaceIdentityIR(
        name=marketplace.name,
        description=marketplace.description,
        industry=marketplace.industry,
    )
    theme = ThemeIR(
        primary=marketplace.theme.primary,
        accent=marketplace.theme.accent,
        neutral=marketplace.theme.neutral,
        font=marketplace.theme.font,
        radius=marketplace.theme.radius,
        logo_emoji=marketplace.theme.logo_emoji,
        voice=marketplace.theme.voice,
    )

    pages = derive_pages(entities, operations, auth, discovery)
    navigation = derive_navigation(entities, operations, pages)

    return FrontendIR(
        marketplace=identity,
        entities=entities,
        operations=operations,
        pages=pages,
        navigation=navigation,
        auth=auth,
        discovery=discovery,
        schemas=schemas,
        spec_hash=spec_hash,
        generator_version=generator_version,
        theme=theme,
    )


# ── Entity building ───────────────────────────────────────────────────


def _build_entity(raw) -> EntityIR:
    sections: list[SectionIR] = []
    for s in raw.sections:
        fields: list[FieldIR] = []
        for f in s.fields:
            ft: FieldType = f.field_type  # type: ignore[assignment]
            fields.append(
                FieldIR(
                    name=f.name,
                    label=f.label,
                    field_type=ft,
                    component=FIELD_TYPE_TO_COMPONENT.get(ft, "TextInput"),
                    required=f.required,
                    options=f.options,
                    visibility=f.visibility,  # type: ignore[arg-type]
                    searchable=f.searchable,
                    ts_type=FIELD_TYPE_TO_TS.get(ft, "string"),
                )
            )
        sections.append(
            SectionIR(
                name=s.name,
                slug=slug_to_kebab(
                    re.sub(r"[^a-z0-9]+", "_", s.name.lower()).strip("_")
                ),
                fields=tuple(fields),
            )
        )

    return EntityIR(
        slug=raw.slug,
        name=raw.name,
        role=raw.role,
        sections=tuple(sections),
        permissions=PermissionsIR(
            can_list=raw.permissions.can_list,
            can_search=raw.permissions.can_search,
            can_initiate_conversation=raw.permissions.can_initiate_conversation,
            can_receive_conversation=raw.permissions.can_receive_conversation,
            can_share_private_assets=raw.permissions.can_share_private_assets,
            requires_onboarding=raw.permissions.requires_onboarding,
            requires_approval=raw.permissions.requires_approval,
            visible_in_search=raw.permissions.visible_in_search,
        ),
        onboarding=OnboardingIR(
            requires_approval=raw.onboarding.requires_approval,
            approval_type=raw.onboarding.approval_type,
            document_upload_required=raw.onboarding.document_upload_required,
            ai_extraction_enabled=raw.onboarding.ai_extraction_enabled,
            ai_profile_generation=raw.onboarding.ai_profile_generation,
            profile_completeness_threshold=raw.onboarding.profile_completeness_threshold,
        ),
    )


# ── Schema building ───────────────────────────────────────────────────


def _build_schemas(openapi: RawOpenAPI) -> tuple[SchemaIR, ...]:
    result: list[SchemaIR] = []
    for name, raw_schema in sorted(openapi.schemas.items()):
        props = tuple(
            SchemaPropertyIR(
                name=p.name,
                ts_type=p.type_hint,
                required=p.required,
                nullable=p.nullable,
            )
            for p in raw_schema.properties
        )
        ts_alias = _resolve_freeform_alias(raw_schema.raw) if not props else None
        result.append(SchemaIR(name=name, properties=props, ts_alias=ts_alias))
    return tuple(result)


def _resolve_freeform_alias(raw: dict) -> str | None:
    """Resolve a TS type for a schema with no top-level ``properties``.

    Returns ``None`` when the default ``Record<string, unknown>`` fallback is
    fine. Otherwise returns the proper TS expression — currently this catches
    ``type: "array"`` (e.g. ``JSONList``) which would otherwise be mistyped
    as an object.
    """
    schema_type = raw.get("type")
    if schema_type == "array":
        items = raw.get("items", {}) or {}
        if items.get("type") == "object":
            additional = items.get("additionalProperties")
            if additional is True or (isinstance(additional, dict) and not additional):
                return "Array<Record<string, unknown>>"
            if isinstance(additional, dict):
                # Nested $ref or typed values — fall back to unknown[] for safety.
                return "Array<Record<string, unknown>>"
            return "Array<Record<string, unknown>>"
        return "unknown[]"
    return None


# ── Operation building ────────────────────────────────────────────────

_ROLE_PATH_RE = re.compile(r"^/api/roles/([a-z][a-z0-9_-]+)/")

_MODULE_TAG_MAP: dict[str, str] = {
    "auth": "auth",
    "profiles": "profiles",
    "discovery": "discovery",
    "communication": "communication",
    "files": "files",
    "notifications": "notifications",
    "admin": "admin",
    "ai": "ai",
    "setup": "setup",
}

_KIND_PATTERNS: list[tuple[str, str, str]] = [
    ("POST", r"/register$", "register"),
    ("GET", r"/draft$", "getDraft"),
    ("PUT", r"/draft$", "updateDraft"),
    ("POST", r"/draft/submit$", "submitDraft"),
    ("GET", r"/me$", "getMe"),
    ("GET", r"/\{profile_id\}$", "getProfile"),
    ("PUT", r"/\{profile_id\}$", "updateProfile"),
    ("POST", r"/\{profile_id\}/ai-generate$", "aiGenerate"),
    ("POST", r"/\{profile_id\}/ai-approve$", "aiApprove"),
    ("POST", r"/\{profile_id\}/ai-reject$", "aiReject"),
]


def _build_operations(
    openapi: RawOpenAPI,
    entity_slugs: set[str],
    marketplace: RawMarketplace,
) -> tuple[OperationIR, ...]:
    schema_lookup = openapi.schemas
    result: list[OperationIR] = []

    for raw_op in openapi.operations:
        entity_slug: str | None = None
        module = "unknown"
        kind = raw_op.operation_id

        role_match = _ROLE_PATH_RE.match(raw_op.path)
        if role_match:
            slug_candidate = role_match.group(1)
            if slug_candidate in entity_slugs:
                entity_slug = slug_candidate
                module = "profiles"
                kind = _detect_kind(raw_op.method, raw_op.path)

        if module == "unknown":
            for tag in raw_op.tags:
                tag_lower = tag.lower()
                if tag_lower in _MODULE_TAG_MAP:
                    module = _MODULE_TAG_MAP[tag_lower]
                    break

        op_id = _build_operation_id(kind, entity_slug, raw_op.operation_id)
        # Keep ``kind`` aligned with the resolved op_id for non-role operations
        # so derived cache keys / hook names don't leak the noisy FastAPI suffix.
        if not entity_slug:
            kind = op_id

        req_schema = _resolve_schema(raw_op.request_schema_name, schema_lookup)
        resp_schema = _resolve_schema(raw_op.response_schema_name, schema_lookup)

        query_params = tuple(
            SchemaPropertyIR(
                name=qp.name,
                ts_type=qp.type_hint,
                required=qp.required,
            )
            for qp in raw_op.query_params
        )

        result.append(
            OperationIR(
                id=op_id,
                entity_slug=entity_slug,
                module=module,
                kind=kind,
                method=raw_op.method,  # type: ignore[arg-type]
                path=raw_op.path,
                request_schema=req_schema,
                response_schema=resp_schema,
                auth_required=raw_op.auth_required,
                path_params=raw_op.path_params,
                query_params=query_params,
            )
        )

    result = _disambiguate_admin_collisions(result)
    return tuple(sorted(result, key=lambda o: o.id))


def _disambiguate_admin_collisions(ops: list[OperationIR]) -> list[OperationIR]:
    """When two ops share the same id but live in different modules, rename
    the admin one to ``{verb}Admin{Suffix}`` so the API client and hook layers
    can address both.

    Without this, FastAPI's auto-generated IDs collapse paths like
    ``GET /api/profiles/{slug}/{id}`` and ``GET /api/admin/profiles/{id}`` to
    a single ``getProfile`` symbol — the second registration silently shadows
    the first.
    """
    by_id: dict[str, list[OperationIR]] = {}
    for op in ops:
        by_id.setdefault(op.id, []).append(op)

    rewrites: dict[int, str] = {}
    for op_id, group in by_id.items():
        if len(group) <= 1:
            continue
        modules = {o.module for o in group}
        if "admin" not in modules or len(modules) <= 1:
            continue
        # Rename only the admin variant(s); leave the user-facing one alone.
        new_id = _admin_qualified_id(op_id)
        for op in group:
            if op.module == "admin":
                rewrites[id(op)] = new_id

    if not rewrites:
        return ops

    rebuilt: list[OperationIR] = []
    for op in ops:
        new_id = rewrites.get(id(op))
        if new_id is None:
            rebuilt.append(op)
            continue
        # ``kind`` mirrors id for non-role ops so cache keys & hook names
        # follow the rename without manual fix-up downstream.
        rebuilt.append(
            OperationIR(
                id=new_id,
                entity_slug=op.entity_slug,
                module=op.module,
                kind=new_id if not op.entity_slug else op.kind,
                method=op.method,
                path=op.path,
                request_schema=op.request_schema,
                response_schema=op.response_schema,
                auth_required=op.auth_required,
                path_params=op.path_params,
                query_params=op.query_params,
            )
        )
    return rebuilt


def _admin_qualified_id(op_id: str) -> str:
    """Insert ``Admin`` after the leading verb of a camelCase op id.

    >>> _admin_qualified_id("getProfile")
    'getAdminProfile'
    >>> _admin_qualified_id("listConversations")
    'listAdminConversations'
    >>> _admin_qualified_id("updatePrompt")
    'updateAdminPrompt'
    >>> _admin_qualified_id("deleteDocument")
    'deleteAdminDocument'
    """
    prefix_end = next((i for i, c in enumerate(op_id) if c.isupper()), len(op_id))
    if prefix_end == 0 or prefix_end == len(op_id):
        return f"admin{op_id[:1].upper()}{op_id[1:]}"
    return f"{op_id[:prefix_end]}Admin{op_id[prefix_end:]}"


def _detect_kind(method: str, path: str) -> str:
    for m, pattern, kind in _KIND_PATTERNS:
        if method == m and re.search(pattern, path):
            return kind
    return "unknown"


_FASTAPI_AUTO_ID_RE = re.compile(
    r"^(?P<verb>[a-z][a-z0-9_]*?)_api_.+_(?P<method>get|post|put|patch|delete)$"
)


def _to_camel(snake: str) -> str:
    parts = [p for p in snake.split("_") if p]
    if not parts:
        return snake
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _normalise_fastapi_operation_id(raw: str) -> str:
    """Strip the FastAPI auto-generated ``_api_<segments>_<method>`` suffix.

    FastAPI synthesises operation IDs like
    ``bootstrap_api_auth_bootstrap_post`` or
    ``activate_user_api_admin_users__user_id__activate_post`` when no explicit
    ``operation_id`` is declared. The verb at the front (``bootstrap``,
    ``activate_user``, ``get_me``, …) is the meaningful part; the rest is
    routing noise that makes the generated React hook / API function names
    impossible to use from hand-written or agent-filled pages.

    >>> _normalise_fastapi_operation_id("bootstrap_api_auth_bootstrap_post")
    'bootstrap'
    >>> _normalise_fastapi_operation_id("activate_user_api_admin_users__user_id__activate_post")
    'activateUser'
    >>> _normalise_fastapi_operation_id("verify_api_auth_verify_get")
    'verifySession'
    >>> _normalise_fastapi_operation_id("verify_api_auth_me_get")
    'getMe'
    >>> _normalise_fastapi_operation_id("login")
    'login'
    """

    match = _FASTAPI_AUTO_ID_RE.match(raw)
    if not match:
        return raw

    verb = match.group("verb")

    # Disambiguate the two ``verify_…`` auth endpoints which would otherwise
    # both collapse to ``verify``.
    if raw.endswith("_me_get") and verb == "verify":
        return "getMe"
    if raw == "verify_api_auth_verify_get":
        return "verifySession"

    return _to_camel(verb)


def _build_operation_id(kind: str, entity_slug: str | None, fallback: str) -> str:
    if entity_slug:
        pascal = slug_to_pascal(entity_slug)
        if kind.startswith("get") or kind.startswith("update") or kind.startswith("submit"):
            prefix_end = next(
                (i for i, c in enumerate(kind) if c.isupper()), len(kind)
            )
            prefix = kind[:prefix_end]
            suffix = kind[prefix_end:]
            return f"{prefix}{pascal}{suffix}"
        return f"{kind}{pascal}"
    return _normalise_fastapi_operation_id(fallback)


def _resolve_schema(
    name: str | None,
    schemas: dict[str, RawSchema],
) -> SchemaIR | None:
    if not name or name not in schemas:
        return None
    raw = schemas[name]
    props = tuple(
        SchemaPropertyIR(
            name=p.name,
            ts_type=p.type_hint,
            required=p.required,
            nullable=p.nullable,
        )
        for p in raw.properties
    )
    return SchemaIR(name=name, properties=props)


# ── Hashing ───────────────────────────────────────────────────────────


def _compute_combined_hash(openapi: RawOpenAPI, marketplace: RawMarketplace) -> str:
    canonical = json.dumps(
        {
            "operations": [
                {"id": o.operation_id, "method": o.method, "path": o.path}
                for o in openapi.operations
            ],
            "schemas": sorted(openapi.schemas.keys()),
            "marketplace_name": marketplace.name,
            "entities": [e.slug for e in marketplace.entities],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
