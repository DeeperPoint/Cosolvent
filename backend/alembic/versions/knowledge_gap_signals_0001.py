"""Knowledge gap signals (curatorial pull loop).

Records questions the reference library could not answer, so curators know what
authoritative content is missing. Written by the domain-Q&A path.

Revision ID: knowledge_gap_signals_0001
Revises: 0002_deal_story_tables
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "knowledge_gap_signals_0001"
down_revision = "0002_deal_story_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_gap_signals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query TEXT NOT NULL,
            vertical TEXT NULL,
            filters JSONB NOT NULL DEFAULT '{}'::jsonb,
            reason TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_gap_signals_created_at "
        "ON knowledge_gap_signals (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_gap_signals_created_at")
    op.execute("DROP TABLE IF EXISTS knowledge_gap_signals")
