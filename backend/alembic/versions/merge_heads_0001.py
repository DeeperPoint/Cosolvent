"""Merge the marketplace and knowledge migration heads into one.

The graph had two heads after the reference-library/Q&A work landed on a
separate branch from the regenerated marketplace snapshot:
  * mkt_fdc097f304d2        (marketplace metadata)
  * knowledge_gap_signals_0001 (reference-library gap signals)
This is a no-op merge revision so `alembic upgrade head` resolves to a single head.

Revision ID: merge_heads_0001
Revises: mkt_fdc097f304d2, knowledge_gap_signals_0001
Create Date: 2026-07-26
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "merge_heads_0001"
down_revision = ("mkt_fdc097f304d2", "knowledge_gap_signals_0001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
