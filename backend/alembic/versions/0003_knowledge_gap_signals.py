"""knowledge_gap_signals table (Loop-2 / GAP-14 pull signals).

Idempotent: creates the table only if it does not already exist, so it is safe to
apply alongside the marketplace auto-migrations.

Revision ID: 0003_knowledge_gap_signals
Revises: 0002_deal_story_tables
"""

from __future__ import annotations

from alembic import op

revision = "0003_knowledge_gap_signals"
down_revision = "0002_deal_story_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_gap_signals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query TEXT NOT NULL,
            topic_needed TEXT NOT NULL DEFAULT '',
            jurisdiction_needed TEXT NOT NULL DEFAULT '',
            gap_description TEXT NOT NULL DEFAULT '',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_gap_signals_status "
        "ON knowledge_gap_signals (status, created_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_gap_signals;")
