"""Deterministic file writer with manifest tracking for the frontend compiler."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_FILENAME = ".generated-manifest.json"

MANAGED_PREFIXES = (
    "src/generated/",
)


def write_frontend(
    output_dir: Path,
    artifacts: dict[str, str],
    *,
    spec_hash: str,
    generator_version: str,
    clean: bool = False,
) -> dict[str, list[str]]:
    """Write generated artifacts and update manifest.

    Returns a dict with ``generated``, ``removed``, and ``skipped`` file lists.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    old_manifest = _load_manifest(output_dir)
    old_managed: set[str] = set()
    if old_manifest:
        old_managed = {
            f for f in old_manifest.get("generated_files", []) if _is_managed(f)
        }

    generated: list[str] = []
    skipped: list[str] = []

    for rel, content in sorted(artifacts.items()):
        _validate_relative_path(rel)
        target = (output_dir / rel).resolve()
        if output_dir not in target.parents and target != output_dir:
            raise ValueError(f"Refusing to write outside output dir: {rel}")

        if not _is_managed(rel) and target.exists() and not clean:
            skipped.append(rel)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        generated.append(rel)

    new_managed = {f for f in generated if _is_managed(f)}
    stale = old_managed - new_managed - {f for f in skipped if _is_managed(f)}
    removed: list[str] = []
    for rel in sorted(stale):
        target = output_dir / rel
        if target.exists() and target.is_file():
            target.unlink()
            removed.append(rel)

    _write_manifest(
        output_dir,
        spec_hash=spec_hash,
        generator_version=generator_version,
        generated_files=sorted(set(generated) | set(skipped)),
    )

    return {
        "generated": sorted(generated),
        "removed": sorted(removed),
        "skipped": sorted(skipped),
    }


def _is_managed(relative_path: str) -> bool:
    return any(relative_path.startswith(p) for p in MANAGED_PREFIXES)


def _load_manifest(output_dir: Path) -> dict | None:
    path = output_dir / MANIFEST_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_manifest(
    output_dir: Path,
    *,
    spec_hash: str,
    generator_version: str,
    generated_files: list[str],
) -> None:
    manifest = {
        "generator": "cosolvent-frontend-compiler",
        "generator_version": generator_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_hash": spec_hash,
        "generated_files": sorted(generated_files),
    }
    path = output_dir / MANIFEST_FILENAME
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_relative_path(relative_path: str) -> None:
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {relative_path}")
    if ".." in rel.parts:
        raise ValueError(f"Parent directory traversal is not allowed: {relative_path}")
