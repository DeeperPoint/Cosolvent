"""Merge the two heads left by the activity tables and the marketplace snapshot.

`alembic upgrade head` requires a single head, and the graph had two, both
branching from `merge_heads_0002`:
  * 0008_activity_match_history         (activity record and scoring history)
  * mkt_8b6cf8bc4e34                    (generated marketplace snapshot)

The two branches touch disjoint tables — `activity_events`, `match_runs` and
`match_ledger` on one side, `marketplace_roles` and
`marketplace_role_permissions` on the other — so joining them needs no schema
change. This is a no-op merge revision, the same pattern as `merge_heads_0002`.

Revision ID: merge_heads_0003
Revises: 0008_activity_match_history, mkt_8b6cf8bc4e34
Create Date: 2026-10-21
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "merge_heads_0003"
down_revision = (
    "0008_activity_match_history",
    "mkt_8b6cf8bc4e34",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
