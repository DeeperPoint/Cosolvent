from __future__ import annotations

from pathlib import Path

from .manifest import is_managed_path, stale_managed_files


def write_artifacts(
    root: Path,
    artifacts: dict[str, str],
    *,
    keep_paths: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    root = root.resolve()
    generated_files: list[str] = []
    keep_paths = keep_paths or set()

    for rel, content in artifacts.items():
        _validate_relative_path(rel)
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Refusing to write outside project root: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        generated_files.append(rel)

    stale = stale_managed_files(root, set(generated_files) | keep_paths)
    removed_files: list[str] = []
    for rel in stale:
        if not is_managed_path(rel):
            continue
        target = (root / rel).resolve()
        if target.exists() and target.is_file():
            target.unlink()
            removed_files.append(rel)

    return sorted(generated_files), sorted(removed_files)


def _validate_relative_path(relative_path: str) -> None:
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {relative_path}")
    if ".." in rel.parts:
        raise ValueError(f"Parent directory traversal is not allowed: {relative_path}")
