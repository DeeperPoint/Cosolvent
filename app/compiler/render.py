from __future__ import annotations

import keyword
import re
from pprint import pformat
from textwrap import dedent

from .ir import CompilerIR

GENERATOR_VERSION = "1.0.0"


def render_artifacts(ir: CompilerIR) -> tuple[dict[str, str], str, str]:
    migration_revision = f"mkt_{ir.spec_hash[:12]}"
    migration_path = f"alembic/versions/auto_marketplace_{migration_revision}.py"

    artifacts = {
        "app/generated/__init__.py": _render_generated_init(ir),
        "app/generated/marketplace_spec.py": _render_marketplace_spec(ir),
        "app/generated/enums.py": _render_enums(ir),
        "app/generated/role_registry.py": _render_role_registry(ir),
        "app/generated/policy_matrix.py": _render_policy_matrix(ir),
        "app/generated/profile_models.py": _render_profile_models(ir),
        "app/generated/role_alias_router.py": _render_role_alias_router(ir),
        migration_path: _render_migration(ir, migration_revision),
    }
    return artifacts, migration_revision, migration_path


def _render_generated_init(ir: CompilerIR) -> str:
    return (
        "\"\"\"Generated marketplace artifacts.\n\n"
        f"spec_hash={ir.spec_hash}\n"
        f"generator_version={GENERATOR_VERSION}\n"
        "\"\"\"\n"
    )


def _render_marketplace_spec(ir: CompilerIR) -> str:
    return (
        "\"\"\"Generated marketplace specification snapshot.\"\"\"\n\n"
        f'SPEC_HASH = "{ir.spec_hash}"\n'
        f'GENERATOR_VERSION = "{GENERATOR_VERSION}"\n'
        f"MARKETPLACE_SPEC = {pformat(ir.config, sort_dicts=True, width=100)}\n"
    )


def _render_role_registry(ir: CompilerIR) -> str:
    role_registry = {
        role.slug: {
            "name": role.name,
            "role_kind": role.role_kind,
            "permissions": role.permissions,
            "onboarding": role.onboarding,
        }
        for role in ir.roles
    }
    role_slugs = [role.slug for role in ir.roles]
    return (
        "\"\"\"Generated role registry for this marketplace build.\"\"\"\n\n"
        f'SPEC_HASH = "{ir.spec_hash}"\n'
        f"ROLE_SLUGS = {pformat(role_slugs, sort_dicts=True, width=100)}\n"
        f"ROLE_REGISTRY = {pformat(role_registry, sort_dicts=True, width=100)}\n"
    )


def _render_policy_matrix(ir: CompilerIR) -> str:
    permissions = {role.slug: role.permissions for role in ir.roles}
    return (
        "\"\"\"Generated policy matrix derived from marketplace config.\"\"\"\n\n"
        f'SPEC_HASH = "{ir.spec_hash}"\n'
        f"PERMISSIONS_BY_ROLE = {pformat(permissions, sort_dicts=True, width=100)}\n"
        f"COMMUNICATION_RULES = {pformat(ir.communication_rules, sort_dicts=True, width=100)}\n"
        f"DISCOVERY_FILTER_FIELDS = {pformat(ir.filter_fields, sort_dicts=True, width=100)}\n"
    )


def _render_profile_models(ir: CompilerIR) -> str:
    schema_map = {
        role.slug: {"sections": role.sections}
        for role in ir.roles
    }
    return (
        "\"\"\"Generated profile model metadata for runtime introspection.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        f'SPEC_HASH = "{ir.spec_hash}"\n'
        f"PROFILE_MODEL_DEFS: dict[str, dict[str, Any]] = {pformat(schema_map, sort_dicts=True, width=100)}\n\n\n"
        "def profile_sections_for(role_slug: str) -> list[dict[str, Any]]:\n"
        "    role = PROFILE_MODEL_DEFS.get(role_slug, {})\n"
        "    return role.get(\"sections\", [])\n"
    )


def _render_enums(ir: CompilerIR) -> str:
    option_defs, _ = _collect_option_enum_defs(ir)
    role_slugs = [role.slug for role in ir.roles]
    role_kinds = sorted({str(role.role_kind) for role in ir.roles})
    approval_types = sorted({str(role.onboarding.get("approval_type", "manual")) for role in ir.roles})
    field_types = sorted(
        {
            str(field.get("type", "text"))
            for role in ir.roles
            for section in role.sections
            for field in section.get("fields", [])
        }
    )
    visibilities = sorted(
        {
            str(field.get("visibility", "public"))
            for role in ir.roles
            for section in role.sections
            for field in section.get("fields", [])
        }
    )

    enums = [
        _render_str_enum("ParticipantTypeEnum", role_slugs),
        _render_str_enum("RoleKindEnum", role_kinds),
        _render_str_enum("ApprovalTypeEnum", approval_types),
        _render_str_enum("FieldTypeEnum", field_types),
        _render_str_enum("FieldVisibilityEnum", visibilities),
        _render_str_enum("DraftStatusEnum", ["draft"]),
        _render_str_enum("ProfileStatusEnum", ["active", "pending", "suspended", "rejected"]),
        _render_str_enum("SubmitStatusEnum", ["pending_review", "active"]),
        _render_str_enum("AIProfileStatusEnum", ["none", "generated", "approved", "rejected"]),
    ]
    for option_def in option_defs:
        enums.append(_render_str_enum(option_def["class_name"], option_def["values"]))

    exported_names = [
        "ParticipantTypeEnum",
        "RoleKindEnum",
        "ApprovalTypeEnum",
        "FieldTypeEnum",
        "FieldVisibilityEnum",
        "DraftStatusEnum",
        "ProfileStatusEnum",
        "SubmitStatusEnum",
        "AIProfileStatusEnum",
    ] + [option_def["class_name"] for option_def in option_defs]

    return (
        "\"\"\"Generated enum definitions for marketplace API/runtime contracts.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "from enum import StrEnum\n\n"
        f'SPEC_HASH = "{ir.spec_hash}"\n\n\n'
        + "\n\n\n".join(enums)
        + "\n\n\n"
        + "__all__ = [\n"
        + "".join(f'    "{name}",\n' for name in exported_names)
        + "]\n"
    )


def _camel_for_slug(slug: str) -> str:
    parts = [part for part in slug.replace("-", "_").split("_") if part]
    if not parts:
        return "Role"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _camel_for_name(value: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    if not parts:
        return "Field"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _field_annotation(field_type: str, option_enum_name: str | None = None) -> str:
    mapping = {
        "text": "str",
        "rich_text": "str",
        "number": "float",
        "select": "str",
        "multi_select": "list[str]",
        "date": "str",
        "file": "str",
        "files": "list[str]",
        "location": "dict[str, Any]",
    }
    if field_type == "select" and option_enum_name:
        return option_enum_name
    if field_type == "multi_select" and option_enum_name:
        return f"list[{option_enum_name}]"
    return mapping.get(field_type, "str")


def _collect_role_fields(role) -> tuple[list[dict], bool]:
    deduped: dict[str, dict] = {}
    all_valid = True
    for section in role.sections:
        for field in section.get("fields", []):
            field_name = str(field.get("name", ""))
            if not field_name:
                continue
            if not field_name.isidentifier() or keyword.iskeyword(field_name):
                all_valid = False
            deduped[field_name] = field
    return list(deduped.values()), all_valid


def _enum_member_name(value: str, index: int, used_names: set[str]) -> str:
    candidate = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not candidate:
        candidate = f"VALUE_{index}"
    if candidate[0].isdigit():
        candidate = f"VALUE_{candidate}"
    if keyword.iskeyword(candidate.lower()):
        candidate = f"{candidate}_VALUE"
    if candidate in used_names:
        suffix = 2
        base = candidate
        while f"{base}_{suffix}" in used_names:
            suffix += 1
        candidate = f"{base}_{suffix}"
    used_names.add(candidate)
    return candidate


def _render_str_enum(class_name: str, values: list[str]) -> str:
    ordered_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered_values.append(normalized)

    member_lines: list[str] = []
    used_member_names: set[str] = set()
    for index, value in enumerate(ordered_values, start=1):
        member_name = _enum_member_name(value, index, used_member_names)
        member_lines.append(f"    {member_name} = {value!r}")
    body = "\n".join(member_lines) if member_lines else "    pass"
    return f"class {class_name}(StrEnum):\n{body}"


def _collect_option_enum_defs(ir: CompilerIR) -> tuple[list[dict[str, object]], dict[tuple[str, str], str]]:
    option_defs: list[dict[str, object]] = []
    option_lookup: dict[tuple[str, str], str] = {}
    used_class_names: set[str] = set()

    for role in ir.roles:
        class_prefix = _camel_for_slug(role.slug)
        role_fields, _ = _collect_role_fields(role)
        for field in role_fields:
            field_name = str(field.get("name", ""))
            field_type = str(field.get("type", "text"))
            raw_options = field.get("options")
            if field_type not in {"select", "multi_select"}:
                continue
            if not isinstance(raw_options, list) or not raw_options:
                continue

            class_name = f"{class_prefix}{_camel_for_name(field_name)}Option"
            if class_name in used_class_names:
                suffix = 2
                while f"{class_name}{suffix}" in used_class_names:
                    suffix += 1
                class_name = f"{class_name}{suffix}"
            used_class_names.add(class_name)

            values = [str(option) for option in raw_options]
            option_defs.append(
                {
                    "role_slug": role.slug,
                    "field_name": field_name,
                    "class_name": class_name,
                    "values": values,
                }
            )
            option_lookup[(role.slug, field_name)] = class_name
    return option_defs, option_lookup


def _render_role_alias_router(ir: CompilerIR) -> str:
    _, option_lookup = _collect_option_enum_defs(ir)
    used_enums: set[str] = {"AIProfileStatusEnum", "DraftStatusEnum", "ParticipantTypeEnum", "ProfileStatusEnum"}
    role_handlers: list[str] = []
    role_model_blocks: list[str] = []
    for role in ir.roles:
        fn_slug = role.slug.replace("-", "_")
        class_prefix = _camel_for_slug(role.slug)
        input_fields_model = f"{class_prefix}DraftFields"
        output_fields_model = f"{class_prefix}ProfileFields"
        request_model = f"{class_prefix}DraftUpdateRequest"
        draft_response_model = f"{class_prefix}DraftResponse"
        profile_response_model = f"{class_prefix}ProfileResponse"
        submit_pending_response_model = f"{class_prefix}SubmitPendingResponse"
        submit_active_response_model = f"{class_prefix}SubmitActiveResponse"
        submit_response_model = f"{class_prefix}SubmitResponse"
        role_fields, all_valid_identifiers = _collect_role_fields(role)

        if all_valid_identifiers and role_fields:
            input_field_lines = []
            output_field_lines = []
            for field in role_fields:
                field_name = str(field.get("name"))
                option_enum_name = option_lookup.get((role.slug, field_name))
                if option_enum_name:
                    used_enums.add(option_enum_name)
                annotation = _field_annotation(str(field.get("type", "text")), option_enum_name)
                if bool(field.get("required", False)):
                    input_field_lines.append(f"    {field_name}: {annotation}")
                else:
                    input_field_lines.append(f"    {field_name}: {annotation} | None = None")
                # Response payloads can be partial (new draft or visibility-filtered profile).
                output_field_lines.append(f"    {field_name}: {annotation} | None = None")
            input_fields_body = "\n".join(input_field_lines) if input_field_lines else "    pass"
            output_fields_body = "\n".join(output_field_lines) if output_field_lines else "    pass"
            input_field_type = input_fields_model
            output_field_type = output_fields_model
            role_model_blocks.append(
                (
                    f"class {input_fields_model}(BaseModel):\n"
                    f"{input_fields_body}\n\n\n"
                    f"class {output_fields_model}(BaseModel):\n"
                    f"{output_fields_body}\n\n\n"
                    f"class {request_model}(BaseModel):\n"
                    f"    fields: {input_field_type}\n\n\n"
                    f"class {draft_response_model}(BaseModel):\n"
                    f"    id: str\n"
                    f"    user_id: str\n"
                    f"    participant_type: ParticipantTypeEnum\n"
                    f"    status: DraftStatusEnum\n"
                    f"    fields: {output_field_type}\n"
                    f"    created_at: str | None = None\n"
                    f"    updated_at: str | None = None\n\n\n"
                    f"class {profile_response_model}(BaseModel):\n"
                    f"    id: str\n"
                    f"    user_id: str\n"
                    f"    participant_type: ParticipantTypeEnum\n"
                    f"    status: ProfileStatusEnum\n"
                    f"    fields: {output_field_type}\n"
                    f"    ai_profile: str | None = None\n"
                    f"    ai_profile_draft: str | None = None\n"
                    f"    ai_profile_status: AIProfileStatusEnum = AIProfileStatusEnum.NONE\n"
                    f"    ai_profile_updated_at: str | None = None\n"
                    f"    completeness: int = 0\n"
                    f"    created_at: str | None = None\n"
                    f"    updated_at: str | None = None\n\n\n"
                    f"class {submit_pending_response_model}(BaseModel):\n"
                    f"    status: Literal[\"pending_review\"]\n"
                    f"    application_id: str\n\n\n"
                    f"class {submit_active_response_model}(BaseModel):\n"
                    f"    status: Literal[\"active\"]\n"
                    f"    profile_id: str\n\n\n"
                    f"{submit_response_model} = {submit_pending_response_model} | {submit_active_response_model}\n"
                )
            )
            payload_expr = "_payload_fields(body.fields)"
        else:
            input_field_type = "dict[str, Any]"
            output_field_type = "dict[str, Any]"
            role_model_blocks.append(
                f"class {request_model}(BaseModel):\n"
                f"    fields: {input_field_type}\n\n\n"
                f"class {draft_response_model}(BaseModel):\n"
                f"    id: str\n"
                f"    user_id: str\n"
                f"    participant_type: ParticipantTypeEnum\n"
                f"    status: DraftStatusEnum\n"
                f"    fields: {output_field_type}\n"
                f"    created_at: str | None = None\n"
                f"    updated_at: str | None = None\n\n\n"
                f"class {profile_response_model}(BaseModel):\n"
                f"    id: str\n"
                f"    user_id: str\n"
                f"    participant_type: ParticipantTypeEnum\n"
                f"    status: ProfileStatusEnum\n"
                f"    fields: {output_field_type}\n"
                f"    ai_profile: str | None = None\n"
                f"    ai_profile_draft: str | None = None\n"
                f"    ai_profile_status: AIProfileStatusEnum = AIProfileStatusEnum.NONE\n"
                f"    ai_profile_updated_at: str | None = None\n"
                f"    completeness: int = 0\n"
                f"    created_at: str | None = None\n"
                f"    updated_at: str | None = None\n\n\n"
                f"class {submit_pending_response_model}(BaseModel):\n"
                f"    status: Literal[\"pending_review\"]\n"
                f"    application_id: str\n\n\n"
                f"class {submit_active_response_model}(BaseModel):\n"
                f"    status: Literal[\"active\"]\n"
                f"    profile_id: str\n\n\n"
                f"{submit_response_model} = {submit_pending_response_model} | {submit_active_response_model}\n"
            )
            payload_expr = "body.fields"

        role_handlers.append(
            dedent(
                f"""\
                @router.post("/api/roles/{role.slug}/register", response_model={draft_response_model})
                async def register_{fn_slug}(
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.register(user, config)


                @router.get("/api/roles/{role.slug}/draft", response_model={draft_response_model})
                async def get_draft_{fn_slug}(
                    user: dict = Depends(get_current_user),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.get_draft(user)


                @router.put("/api/roles/{role.slug}/draft", response_model={draft_response_model})
                async def update_draft_{fn_slug}(
                    body: {request_model},
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.update_draft(user, {payload_expr}, config)


                @router.post("/api/roles/{role.slug}/draft/submit", response_model={submit_response_model})
                async def submit_draft_{fn_slug}(
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.submit_draft(user, config)


                @router.get("/api/roles/{role.slug}/me", response_model={profile_response_model})
                async def me_{fn_slug}(
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.get_my_profile(user, config)


                @router.get("/api/roles/{role.slug}/{{profile_id}}", response_model={profile_response_model})
                async def get_profile_{fn_slug}(
                    profile_id: str,
                    user: dict | None = Depends(get_optional_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    return await service.get_profile(profile_id, "{role.slug}", config, user)


                @router.put("/api/roles/{role.slug}/{{profile_id}}", response_model={profile_response_model})
                async def update_profile_{fn_slug}(
                    profile_id: str,
                    body: {request_model},
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.update_profile(profile_id, user, {payload_expr}, config)


                @router.post("/api/roles/{role.slug}/{{profile_id}}/ai-generate", response_model=AIProfileActionResponse)
                async def ai_generate_{fn_slug}(
                    profile_id: str,
                    user: dict = Depends(get_current_user),
                    config: MarketplaceConfig = Depends(get_config),
                ):
                    _ensure_role_user(user, "{role.slug}")
                    return await service.ai_generate_profile(profile_id, user, config)


                @router.post("/api/roles/{role.slug}/{{profile_id}}/ai-approve", response_model=AIProfileActionResponse)
                async def ai_approve_{fn_slug}(
                    profile_id: str,
                    _admin: dict = Depends(require_admin),
                ):
                    return await service.ai_approve_profile(profile_id)


                @router.post("/api/roles/{role.slug}/{{profile_id}}/ai-reject", response_model=AIProfileActionResponse)
                async def ai_reject_{fn_slug}(
                    profile_id: str,
                    _admin: dict = Depends(require_admin),
                ):
                    return await service.ai_reject_profile(profile_id)
                """
            )
        )

    roles = [role.slug for role in ir.roles]
    rendered_models = "\n\n".join(role_model_blocks)
    rendered_handlers = "\n\n".join(role_handlers)
    enum_imports = ", ".join(sorted(used_enums))
    header = f"""\"\"\"Generated role alias router.

These aliases provide stable role-specific endpoints while preserving
the generic /api/profiles/{{type_slug}}/... routes.
\"\"\"

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_config, get_current_user, get_optional_user, require_admin
from app.generated.enums import {enum_imports}
from app.core.marketplace_config import MarketplaceConfig
from app.modules.profiles import service
from app.modules.profiles.schemas import AIProfileActionResponse

SPEC_HASH = "{ir.spec_hash}"
ROLE_SLUGS = {pformat(roles, sort_dicts=True, width=100)}

router = APIRouter(tags=["profiles"])


def _ensure_role_user(user: dict, role_slug: str) -> None:
    if user.get("role") == "admin":
        return
    participant_type = user.get("participant_type")
    if participant_type != role_slug:
        raise HTTPException(
            status_code=403,
            detail=f"Role alias '{{role_slug}}' does not match your participant type '{{participant_type}}'",
        )


def _payload_fields(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True, mode="json")
    return dict(value)
"""
    return header.rstrip() + "\n\n" + rendered_models.rstrip() + "\n\n" + rendered_handlers.rstrip() + "\n"


def _render_migration(ir: CompilerIR, migration_revision: str) -> str:
    roles = []
    permissions = []
    onboarding = []
    communication = []
    profile_fields = []

    for role in ir.roles:
        roles.append({"slug": role.slug, "name": role.name, "role_kind": role.role_kind})
        permission_row = {"slug": role.slug}
        permission_row.update(role.permissions)
        permissions.append(permission_row)
        onboarding_row = {"slug": role.slug}
        onboarding_row.update(role.onboarding)
        onboarding.append(onboarding_row)

        ordinal = 0
        for section in role.sections:
            section_name = section.get("name", "Section")
            for field in section.get("fields", []):
                ordinal += 1
                profile_fields.append(
                    {
                        "slug": role.slug,
                        "section_name": section_name,
                        "field_name": field.get("name"),
                        "field_label": field.get("label"),
                        "field_type": field.get("type"),
                        "visibility": field.get("visibility", "public"),
                        "required": bool(field.get("required", False)),
                        "searchable": bool(field.get("searchable", False)),
                        "options_json": field.get("options"),
                        "accepted_types_json": field.get("accepted_types"),
                        "ordinal": ordinal,
                    }
                )

    for rule in ir.communication_rules:
        communication.append(
            {
                "initiator": rule["initiator"],
                "receiver": rule["receiver"],
                "requires_approval": bool(rule.get("requires_approval", True)),
            }
        )

    roles_repr = repr(roles)
    permissions_repr = repr(permissions)
    onboarding_repr = repr(onboarding)
    communication_repr = repr(communication)
    profile_fields_repr = repr(profile_fields)

    return dedent(
        f"""\
        \"\"\"Generated marketplace metadata migration.

        Revision ID: {migration_revision}
        \"\"\"

        from __future__ import annotations

        import json

        from alembic import op
        import sqlalchemy as sa

        revision = "{migration_revision}"
        down_revision = "0001_postgres_pgvector"
        branch_labels = None
        depends_on = None

        ROLES = {roles_repr}
        ROLE_PERMISSIONS = {permissions_repr}
        ONBOARDING_RULES = {onboarding_repr}
        COMMUNICATION_RULES = {communication_repr}
        PROFILE_FIELD_DEFS = {profile_fields_repr}
        SPEC_HASH = "{ir.spec_hash}"
        BUILD_MODE = "{ir.mode}"
        GENERATOR_VERSION = "{GENERATOR_VERSION}"


        def upgrade() -> None:
            op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_roles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role_kind TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            \"\"\")
            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_role_permissions (
                role_id UUID PRIMARY KEY REFERENCES marketplace_roles(id) ON DELETE CASCADE,
                can_list BOOLEAN NOT NULL DEFAULT FALSE,
                can_search BOOLEAN NOT NULL DEFAULT FALSE,
                can_initiate_conversation BOOLEAN NOT NULL DEFAULT FALSE,
                can_receive_conversation BOOLEAN NOT NULL DEFAULT FALSE,
                can_share_private_assets BOOLEAN NOT NULL DEFAULT FALSE,
                requires_onboarding BOOLEAN NOT NULL DEFAULT TRUE,
                requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
                visible_in_search BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            \"\"\")
            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_onboarding_rules (
                role_id UUID PRIMARY KEY REFERENCES marketplace_roles(id) ON DELETE CASCADE,
                requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
                approval_type TEXT NOT NULL DEFAULT 'manual',
                document_upload_required BOOLEAN NOT NULL DEFAULT FALSE,
                ai_extraction_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                ai_profile_generation BOOLEAN NOT NULL DEFAULT FALSE,
                welcome_email_on_approval BOOLEAN NOT NULL DEFAULT TRUE,
                profile_completeness_threshold INTEGER NOT NULL DEFAULT 100,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            \"\"\")
            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_communication_rules (
                initiator_role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
                receiver_role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
                requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (initiator_role_id, receiver_role_id)
            )
            \"\"\")
            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_profile_field_defs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
                section_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_label TEXT NOT NULL,
                field_type TEXT NOT NULL,
                visibility TEXT NOT NULL DEFAULT 'public',
                required BOOLEAN NOT NULL DEFAULT FALSE,
                searchable BOOLEAN NOT NULL DEFAULT FALSE,
                options_json JSONB NULL,
                accepted_types_json JSONB NULL,
                ordinal INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (role_id, section_name, field_name)
            )
            \"\"\")
            op.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS marketplace_builds (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                spec_hash TEXT NOT NULL UNIQUE,
                mode TEXT NOT NULL,
                generator_version TEXT NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            \"\"\")
            op.execute("CREATE INDEX IF NOT EXISTS ix_marketplace_roles_slug ON marketplace_roles (slug)")
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_marketplace_profile_field_defs_lookup "
                "ON marketplace_profile_field_defs (role_id, section_name, ordinal)"
            )

            conn = op.get_bind()

            for row in ROLES:
                conn.execute(
                    sa.text(
                        \"\"\"
                        INSERT INTO marketplace_roles (slug, name, role_kind, is_active, updated_at)
                        VALUES (:slug, :name, :role_kind, TRUE, NOW())
                        ON CONFLICT (slug) DO UPDATE
                        SET name = EXCLUDED.name,
                            role_kind = EXCLUDED.role_kind,
                            is_active = TRUE,
                            updated_at = NOW()
                        \"\"\"
                    ),
                    row,
                )

            for row in ROLE_PERMISSIONS:
                conn.execute(
                    sa.text(
                        \"\"\"
                        INSERT INTO marketplace_role_permissions (
                            role_id,
                            can_list,
                            can_search,
                            can_initiate_conversation,
                            can_receive_conversation,
                            can_share_private_assets,
                            requires_onboarding,
                            requires_approval,
                            visible_in_search,
                            updated_at
                        )
                        SELECT
                            r.id,
                            :can_list,
                            :can_search,
                            :can_initiate_conversation,
                            :can_receive_conversation,
                            :can_share_private_assets,
                            :requires_onboarding,
                            :requires_approval,
                            :visible_in_search,
                            NOW()
                        FROM marketplace_roles r
                        WHERE r.slug = :slug
                        ON CONFLICT (role_id) DO UPDATE
                        SET can_list = EXCLUDED.can_list,
                            can_search = EXCLUDED.can_search,
                            can_initiate_conversation = EXCLUDED.can_initiate_conversation,
                            can_receive_conversation = EXCLUDED.can_receive_conversation,
                            can_share_private_assets = EXCLUDED.can_share_private_assets,
                            requires_onboarding = EXCLUDED.requires_onboarding,
                            requires_approval = EXCLUDED.requires_approval,
                            visible_in_search = EXCLUDED.visible_in_search,
                            updated_at = NOW()
                        \"\"\"
                    ),
                    row,
                )

            for row in ONBOARDING_RULES:
                conn.execute(
                    sa.text(
                        \"\"\"
                        INSERT INTO marketplace_onboarding_rules (
                            role_id,
                            requires_approval,
                            approval_type,
                            document_upload_required,
                            ai_extraction_enabled,
                            ai_profile_generation,
                            welcome_email_on_approval,
                            profile_completeness_threshold,
                            updated_at
                        )
                        SELECT
                            r.id,
                            :requires_approval,
                            :approval_type,
                            :document_upload_required,
                            :ai_extraction_enabled,
                            :ai_profile_generation,
                            :welcome_email_on_approval,
                            :profile_completeness_threshold,
                            NOW()
                        FROM marketplace_roles r
                        WHERE r.slug = :slug
                        ON CONFLICT (role_id) DO UPDATE
                        SET requires_approval = EXCLUDED.requires_approval,
                            approval_type = EXCLUDED.approval_type,
                            document_upload_required = EXCLUDED.document_upload_required,
                            ai_extraction_enabled = EXCLUDED.ai_extraction_enabled,
                            ai_profile_generation = EXCLUDED.ai_profile_generation,
                            welcome_email_on_approval = EXCLUDED.welcome_email_on_approval,
                            profile_completeness_threshold = EXCLUDED.profile_completeness_threshold,
                            updated_at = NOW()
                        \"\"\"
                    ),
                    row,
                )

            for row in COMMUNICATION_RULES:
                conn.execute(
                    sa.text(
                        \"\"\"
                        INSERT INTO marketplace_communication_rules (
                            initiator_role_id, receiver_role_id, requires_approval, updated_at
                        )
                        SELECT i.id, r.id, :requires_approval, NOW()
                        FROM marketplace_roles i
                        JOIN marketplace_roles r ON r.slug = :receiver
                        WHERE i.slug = :initiator
                        ON CONFLICT (initiator_role_id, receiver_role_id) DO UPDATE
                        SET requires_approval = EXCLUDED.requires_approval,
                            updated_at = NOW()
                        \"\"\"
                    ),
                    row,
                )

            conn.execute(sa.text("DELETE FROM marketplace_profile_field_defs"))
            for row in PROFILE_FIELD_DEFS:
                payload = dict(row)
                payload["options_json"] = json.dumps(payload["options_json"]) if payload.get("options_json") is not None else None
                payload["accepted_types_json"] = json.dumps(payload["accepted_types_json"]) if payload.get("accepted_types_json") is not None else None
                conn.execute(
                    sa.text(
                        \"\"\"
                        INSERT INTO marketplace_profile_field_defs (
                            role_id,
                            section_name,
                            field_name,
                            field_label,
                            field_type,
                            visibility,
                            required,
                            searchable,
                            options_json,
                            accepted_types_json,
                            ordinal,
                            updated_at
                        )
                        SELECT
                            r.id,
                            :section_name,
                            :field_name,
                            :field_label,
                            :field_type,
                            :visibility,
                            :required,
                            :searchable,
                            CAST(:options_json AS JSONB),
                            CAST(:accepted_types_json AS JSONB),
                            :ordinal,
                            NOW()
                        FROM marketplace_roles r
                        WHERE r.slug = :slug
                        \"\"\"
                    ),
                    payload,
                )

            conn.execute(
                sa.text(
                    \"\"\"
                    INSERT INTO marketplace_builds (spec_hash, mode, generator_version, generated_at)
                    VALUES (:spec_hash, :mode, :generator_version, NOW())
                    ON CONFLICT (spec_hash) DO UPDATE
                    SET mode = EXCLUDED.mode,
                        generator_version = EXCLUDED.generator_version,
                        generated_at = NOW()
                    \"\"\"
                ),
                {{
                    "spec_hash": SPEC_HASH,
                    "mode": BUILD_MODE,
                    "generator_version": GENERATOR_VERSION,
                }},
            )


        def downgrade() -> None:
            op.execute("DELETE FROM marketplace_builds WHERE spec_hash = '{ir.spec_hash}'")
            # Keep metadata tables in place to avoid destructive behavior for previous builds.
        """
    )
