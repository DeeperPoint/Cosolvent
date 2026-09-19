"""Compiler output directories on the checkouts people actually have.

`backend/openapi` and `backend/generated` are tracked symlinks into the repo root,
and neither resolves to a directory on a clean checkout: a fresh clone has no
target yet, and a Windows checkout without symlink support has a placeholder file
where the link should be. Both used to fail the compile with `FileExistsError`.
"""

from __future__ import annotations

import os

import pytest

from app.compiler.fsutil import ensure_output_dir


def test_an_ordinary_missing_directory_is_created(tmp_path):
    target = tmp_path / "openapi"

    assert ensure_output_dir(target) == target
    assert target.is_dir()


def test_an_existing_directory_is_returned_untouched(tmp_path):
    target = tmp_path / "openapi"
    target.mkdir()
    (target / "keep.json").write_text("{}", encoding="utf-8")

    assert ensure_output_dir(target) == target
    assert (target / "keep.json").read_text(encoding="utf-8") == "{}"


def test_a_symlink_whose_target_is_missing_creates_the_target(tmp_path):
    """A fresh clone: the link is committed, the directory it names is not."""
    link = tmp_path / "backend" / "openapi"
    link.parent.mkdir()
    try:
        os.symlink("../openapi", link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this checkout cannot create symlinks")

    resolved = ensure_output_dir(link)

    assert resolved.is_dir()
    assert resolved == (tmp_path / "openapi").resolve()
    # The link itself is left exactly as committed.
    assert link.is_symlink()


def test_a_windows_symlink_placeholder_writes_through_to_its_target(tmp_path):
    """Without symlink support git writes the link as a file naming the target."""
    placeholder = tmp_path / "backend" / "openapi"
    placeholder.parent.mkdir()
    placeholder.write_text("../openapi", encoding="utf-8")

    resolved = ensure_output_dir(placeholder)

    assert resolved.is_dir()
    assert resolved == (tmp_path / "openapi").resolve()
    # The placeholder is tracked content - writing through it must not replace it.
    assert placeholder.is_file()
    assert placeholder.read_text(encoding="utf-8") == "../openapi"


def test_a_real_file_in_the_way_is_reported_not_overwritten(tmp_path):
    """Only a placeholder is followed. Anything else is a genuine collision."""
    blocker = tmp_path / "openapi"
    blocker.write_text('{"paths": {}}\nsecond line\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="is a file, not a directory"):
        ensure_output_dir(blocker)

    assert blocker.read_text(encoding="utf-8").startswith('{"paths"')
