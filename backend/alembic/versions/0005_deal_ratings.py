"""deal_ratings table — post-handoff bidirectional reputation (roadmap §9.2).

Idempotent (CREATE TABLE IF NOT EXISTS), same generic JSONB document-table shape as
``deals``/``notifications``, so it coexists cleanly with the runtime
``metadata.create_all`` path used in development (see 0002_deal_story_tables.py,
which this follows). Chained onto the stable 0001->0002->0003->0004 line rather than
the compiler-generated ``mkt_*`` branch, for the same reason 0002 was: that branch's
history has a dangling revision (see git history "Fix broken Alembic chain") and
hand-written migrations stay off it.

Revision ID: 0005_deal_ratings
Revises: 0004_escape_hatches
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "0005_deal_ratings"
down_revision = "0004_escape_hatches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS deal_ratings (
            id UUID PRIMARY KEY,
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_deal_ratings_data ON deal_ratings USING GIN (data)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS deal_ratings")
