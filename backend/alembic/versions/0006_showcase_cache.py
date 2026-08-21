"""showcase_cache table — pre-computed demo data (MarketForge Phase 6a "Mode 1").

Idempotent (CREATE TABLE IF NOT EXISTS), same generic JSONB document-table shape as
deal_ratings/deals (see 0005_deal_ratings.py, which this follows).

Revision ID: 0006_showcase_cache
Revises: 0005_deal_ratings
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "0006_showcase_cache"
down_revision = "0005_deal_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS showcase_cache (
            id UUID PRIMARY KEY,
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_showcase_cache_data ON showcase_cache USING GIN (data)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS showcase_cache")
