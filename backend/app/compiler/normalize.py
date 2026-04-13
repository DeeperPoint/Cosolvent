from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.core.marketplace_config import MarketplaceConfig

from .ir import CompileMode, CompilerIR, RoleSpec

_ROLE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_RESERVED_ROLE_SLUGS = {
    "admin",
    "auth",
    "search",
    "files",
    "notifications",
    "setup",
    "docs",
    "openapi",
    "roles",
    "ws",
}


def normalize_to_ir(
    raw_config: dict[str, Any] | MarketplaceConfig,
    *,
    project_root: Path,
    mode: CompileMode = "mvp",
) -> CompilerIR:
    config_obj = raw_config if isinstance(raw_config, MarketplaceConfig) else MarketplaceConfig(**raw_config)
    config_dict = config_obj.model_dump()
    _validate_role_slugs(config_obj.type_slugs())

    canonical_json = _canonical_json(config_dict)
    spec_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    roles: list[RoleSpec] = []
    for participant in config_obj.participant_types:
        schema = config_obj.profile_schemas[participant.slug]
        onboarding = config_obj.onboarding[participant.slug]
        roles.append(
            RoleSpec(
                slug=participant.slug,
                name=participant.name,
                role_kind=participant.role,
                permissions=participant.permissions.model_dump(),
                onboarding=onboarding.model_dump(),
                sections=schema.model_dump().get("sections", []),
            )
        )

    return CompilerIR(
        project_root=project_root.resolve(),
        spec_hash=spec_hash,
        canonical_json=canonical_json,
        config=config_dict,
        roles=roles,
        communication_rules=config_dict["communication"]["conversation_rules"],
        filter_fields=config_dict["discovery"]["filter_fields"],
        mode=mode,
    )


def _canonical_json(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_role_slugs(slugs: list[str]) -> None:
    for slug in slugs:
        if not _ROLE_SLUG_RE.match(slug):
            raise ValueError(
                f"Invalid participant slug '{slug}'. Use lowercase letters, numbers, '_' or '-', 2-64 chars."
            )
        if slug in _RESERVED_ROLE_SLUGS:
            raise ValueError(
                f"Participant slug '{slug}' is reserved and cannot be used for generated role aliases."
            )

