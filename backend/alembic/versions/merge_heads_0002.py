"""Merge the three migration heads left by the regenerated marketplace snapshots.

`alembic upgrade head` (what `docker-readme.md` and `docs/dev/getting-started.md`
both tell you to run) requires a single head, and the graph had three:
  * 0007_escape_hatch_provenance        (core schema)
  * mkt_f9192e8ae8e5                    (generated marketplace snapshot)
  * reference_library_chunk_hash        (reference library)

This is a no-op merge revision, the same pattern as `merge_heads_0001`.

Revision ID: merge_heads_0002
Revises: 0007_escape_hatch_provenance, mkt_f9192e8ae8e5, reference_library_chunk_hash
Create Date: 2026-09-19
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "merge_heads_0002"
down_revision = (
    "0007_escape_hatch_provenance",
    "mkt_f9192e8ae8e5",
    "reference_library_chunk_hash",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
