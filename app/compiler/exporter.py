from __future__ import annotations

import tarfile
from pathlib import Path

_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".docker-cache",
    "exports",
}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


def create_export_archive(root: Path, *, export_dir: str, spec_hash: str) -> str:
    root = root.resolve()
    export_root = (root / export_dir).resolve()
    if root not in export_root.parents and export_root != root:
        raise ValueError("export_dir must stay within the project directory")
    export_root.mkdir(parents=True, exist_ok=True)

    file_name = f"marketplace-{spec_hash[:12]}.tar.gz"
    archive_path = export_root / file_name

    with tarfile.open(archive_path, "w:gz") as tar:
        for path in _iter_files(root):
            arcname = path.relative_to(root)
            tar.add(path, arcname=str(arcname))

    return str(archive_path.relative_to(root))


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix in _SKIP_SUFFIXES:
            continue
        yield path

