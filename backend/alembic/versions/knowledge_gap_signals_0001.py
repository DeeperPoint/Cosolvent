"""Knowledge gap signals (curatorial pull loop).

Records questions the reference library could not answer, so curators know what
authoritative content is missing. Written by the domain-Q&A path.

Revision ID: knowledge_gap_signals_0001
Revises: reference_library_0001
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "knowledge_gap_signals_0001"
down_revision = "reference_library_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gap_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("vertical", sa.Text(), nullable=True),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_gap_signals_created_at "
        "ON knowledge_gap_signals (created_at DESC)"
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_gap_signals_created_at", table_name="knowledge_gap_signals")
    op.drop_table("knowledge_gap_signals")
