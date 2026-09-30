"""Filesystem helpers for compiler output paths."""

from __future__ import annotations

import os
from pathlib import Path

# A tracked symlink that git materialised as a placeholder file holds its target
# as one short relative path and nothing else.
_MAX_PLACEHOLDER_BYTES = 256


def ensure_output_dir(directory: Path) -> Path:
    """Return a writable directory for `directory`, creating it when needed.

    `backend/openapi` and `backend/generated` are tracked symlinks pointing at the
    repository root, and two ordinary checkouts break a plain
    `mkdir(parents=True, exist_ok=True)` on them:

    * In a fresh clone the target does not exist yet. `mkdir` finds the dangling
      link is not a directory and raises `FileExistsError`, so `compile` fails on
      a clean tree - Linux included.
    * On Windows without symlink support git writes the link as a small text file
      holding the target path, so the name exists as a regular file.

    Both are resolved by writing to the directory the link names. Nothing already
    in the working tree is replaced or removed.
    """
    if directory.is_symlink() and not directory.exists():
        target = Path(os.path.realpath(directory))
        target.mkdir(parents=True, exist_ok=True)
        return target

    if directory.is_file():
        placeholder_target = _placeholder_target(directory)
        if placeholder_target is None:
            raise RuntimeError(
                f"Cannot write generated output: {directory} is a file, not a directory."
            )
        placeholder_target.mkdir(parents=True, exist_ok=True)
        return placeholder_target

    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _placeholder_target(placeholder: Path) -> Path | None:
    """The directory a git symlink placeholder names, or None if it is a real file."""
    try:
        if placeholder.stat().st_size > _MAX_PLACEHOLDER_BYTES:
            return None
        text = placeholder.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not text or "\n" in text or "\x00" in text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return None
    return (placeholder.parent / candidate).resolve()
