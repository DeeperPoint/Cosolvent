"""The migration graph itself, which three separate bugs have broken.

None of these are caught by the rest of the suite, because every other test runs
against a database built by `metadata.create_all()` rather than by migrations.
They only appear on a first install - the moment it matters most.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# `alembic_version.version_num` is a VARCHAR(32), so a longer id cannot be stored
# and the upgrade fails when it reaches that revision.
MAX_REVISION_ID = 32


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_every_revision_id_fits_the_version_column(script):
    too_long = {
        rev.revision: len(rev.revision)
        for rev in script.walk_revisions()
        if len(rev.revision) > MAX_REVISION_ID
    }
    assert not too_long, f"revision ids exceed VARCHAR({MAX_REVISION_ID}): {too_long}"


def test_the_graph_has_exactly_one_head(script):
    """`alembic upgrade head` - what the docs tell operators to run - needs one."""
    heads = script.get_heads()
    assert len(heads) == 1, f"expected a single head, found {heads}"


def test_every_down_revision_exists(script):
    """A generated migration was once deleted while its child survived, which made
    every alembic command fail with a bare KeyError."""
    known = {rev.revision for rev in script.walk_revisions()}
    missing: dict[str, str] = {}
    for rev in script.walk_revisions():
        for parent in (rev.down_revision or ()) if isinstance(rev.down_revision, tuple) \
                else ([rev.down_revision] if rev.down_revision else []):
            if parent not in known:
                missing[rev.revision] = parent
    assert not missing, f"migrations reference revisions that no longer exist: {missing}"
