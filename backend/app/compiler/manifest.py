from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .render import GENERATOR_VERSION


MANIFEST_PATH = Path("generated/manifest.json")

# Paths the compiler owns and records in the manifest.
MANAGED_PREFIXES = (
    "app/generated/",
    "generated/",
    "openapi/",
    "alembic/versions/auto_marketplace_",
)

# Of those, the ones safe to delete when a later compile no longer produces them.
#
# Alembic migrations are deliberately excluded. Generated code under `app/generated/`
# is a pure projection of the current config — regenerating from a different config
# makes the old files meaningless, so pruning them is correct. A migration is not a
# projection; it is history that may already have been applied to a database, and it
# stays referenced by the revision chain. Pruning those meant that compiling a second
# marketplace config deleted the first one's migration from the working tree — a file
# that is normally committed — leaving a deletion in `git status` that nobody made.
PRUNABLE_PREFIXES = tuple(
    prefix for prefix in MANAGED_PREFIXES if not prefix.startswith("alembic/versions/")
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
    normalized_new_files = {_normalize_manifest_path(path) or path for path in new_files}
    for rel in old.get("generated_files", []):
        raw = str(rel)
        normalized = _normalize_manifest_path(raw)
        if normalized is None:
            continue
        if normalized in normalized_new_files:
            continue
        if is_prunable_path(normalized):
            stale.append(normalized)
    return sorted(set(stale))


def invalid_managed_manifest_entries(root: Path) -> list[str]:
    old = load_manifest(root)
    if not old:
        return []
    invalid: list[str] = []
    for rel in old.get("generated_files", []):
        raw = str(rel)
        if not is_managed_path(raw):
            continue
        if _normalize_manifest_path(raw) is None:
            invalid.append(raw)
    return sorted(set(invalid))


def is_managed_path(relative_path: str) -> bool:
    """True if the compiler generates this path (and records it in the manifest)."""
    return any(relative_path.startswith(prefix) for prefix in MANAGED_PREFIXES)


def is_prunable_path(relative_path: str) -> bool:
    """True if the compiler may delete this path when it is no longer generated.

    Narrower than `is_managed_path` on purpose — see PRUNABLE_PREFIXES.
    """
    return any(relative_path.startswith(prefix) for prefix in PRUNABLE_PREFIXES)


def _normalize_manifest_path(relative_path: str) -> str | None:
    candidate = str(relative_path).strip()
    if not candidate:
        return None
    path = Path(candidate)
    if path.is_absolute():
        return None
    if ".." in path.parts:
        return None
    return path.as_posix()
