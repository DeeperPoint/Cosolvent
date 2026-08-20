"""escape_hatches table (Loop-2 / GAP-14 conditional-gate rules).

Idempotent: creates the table only if it does not already exist, so it is safe to
apply alongside the marketplace auto-migrations and the runtime create_all.

Revision ID: 0004_escape_hatches
Revises: 0003_knowledge_gap_signals
"""

from __future__ import annotations

from alembic import op

revision = "0004_escape_hatches"
down_revision = "0003_knowledge_gap_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS escape_hatches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            vertical TEXT,
            gate_name TEXT NOT NULL,
            condition JSONB NOT NULL DEFAULT '{}'::jsonb,
            rationale TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            hatch_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_escape_hatches_active "
        "ON escape_hatches (status, gate_name);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS escape_hatches;")
