from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


CompileMode = Literal["mvp", "strict"]


@dataclass(frozen=True)
class CompileOptions:
    mode: CompileMode = "mvp"
    export_enabled: bool = True
    export_dir: str = "exports"
    overwrite_policy: Literal["managed"] = "managed"


@dataclass(frozen=True)
class RoleSpec:
    slug: str
    name: str
    role_kind: str
    permissions: dict[str, bool]
    onboarding: dict[str, Any]
    sections: list[dict[str, Any]]


@dataclass(frozen=True)
class CompilerIR:
    project_root: Path
    spec_hash: str
    canonical_json: str
    config: dict[str, Any]
    roles: list[RoleSpec]
    communication_rules: list[dict[str, Any]]
    filter_fields: list[str]
    mode: CompileMode

