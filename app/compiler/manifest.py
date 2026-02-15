from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .render import GENERATOR_VERSION


MANIFEST_PATH = Path("generated/manifest.json")
MANAGED_PREFIXES = (
    "app/generated/",
    "generated/",
    "openapi/",
    "alembic/versions/auto_marketplace_",
)


@dataclass(frozen=True)
class CompileManifest:
    spec_hash: str
    mode: str
    generated_files: list[str]
    migration_revision: str
    export_path: str | None
    generated_at: str
    generator_version: str = GENERATOR_VERSION

    def to_dict(self) -> dict:
        return {
            "spec_hash": self.spec_hash,
            "mode": self.mode,
            "generated_files": self.generated_files,
            "migration_revision": self.migration_revision,
            "export_path": self.export_path,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
        }


def load_manifest(root: Path) -> dict | None:
    path = root / MANIFEST_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_manifest(
    root: Path,
    *,
    spec_hash: str,
    mode: str,
    generated_files: list[str],
    migration_revision: str,
    export_path: str | None,
) -> dict:
    manifest = CompileManifest(
        spec_hash=spec_hash,
        mode=mode,
        generated_files=sorted(generated_files),
        migration_revision=migration_revision,
        export_path=export_path,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    path = root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return manifest.to_dict()


def stale_managed_files(root: Path, new_files: set[str]) -> list[str]:
    old = load_manifest(root)
    if not old:
        return []
    stale: list[str] = []
    for rel in old.get("generated_files", []):
        if rel in new_files:
            continue
        if is_managed_path(rel):
            stale.append(rel)
    return sorted(stale)


def is_managed_path(relative_path: str) -> bool:
    return any(relative_path.startswith(prefix) for prefix in MANAGED_PREFIXES)

