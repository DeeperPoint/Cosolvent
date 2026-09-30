"""Where a generated marketplace migration attaches itself in the graph.

Getting this wrong is not a cosmetic problem: a migration that attaches to a
stale revision creates a second head, and `alembic upgrade head` - the command
the docs give operators - then refuses to run at all.
"""

from __future__ import annotations

from app.compiler.render import resolve_alembic_down_revision

LINEAR = '''revision = "{rev}"
down_revision = "{down}"
'''

MERGE = '''revision = "{rev}"
down_revision = (
    "{first}",
    "{second}",
)
'''


def _versions(tmp_path, files: dict[str, str]):
    versions = tmp_path / "alembic" / "versions"
    versions.mkdir(parents=True)
    for name, text in files.items():
        (versions / f"{name}.py").write_text(text, encoding="utf-8")
    return tmp_path


def test_a_new_migration_follows_the_single_head(tmp_path):
    root = _versions(tmp_path, {
        "base": LINEAR.format(rev="0001_base", down="None").replace('"None"', "None"),
        "mkt_old": LINEAR.format(rev="mkt_old", down="0001_base"),
    })

    assert resolve_alembic_down_revision(root, "mkt_new") == "mkt_old"


def test_a_merge_revision_is_recognised_as_the_head(tmp_path):
    """A merge declares its parents as a tuple, often across several lines. Read
    as 'no parents', each parent still looks like a head and the new migration
    branches off one of them instead of following the merge."""
    root = _versions(tmp_path, {
        "base": LINEAR.format(rev="0001_base", down="None").replace('"None"', "None"),
        "mkt_old": LINEAR.format(rev="mkt_old", down="0001_base"),
        "other": LINEAR.format(rev="other_branch", down="0001_base"),
        "merge": MERGE.format(rev="merge_0001", first="mkt_old", second="other_branch"),
    })

    assert resolve_alembic_down_revision(root, "mkt_new") == "merge_0001"


def test_regenerating_the_same_revision_keeps_its_place(tmp_path):
    root = _versions(tmp_path, {
        "base": LINEAR.format(rev="0001_base", down="None").replace('"None"', "None"),
        "mkt_existing": LINEAR.format(rev="mkt_existing", down="0001_base"),
        "later": LINEAR.format(rev="later_rev", down="mkt_existing"),
    })

    assert resolve_alembic_down_revision(root, "mkt_existing") == "0001_base"
