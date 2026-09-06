"""escape_hatches: structured route provenance (granting_authority, edition, evidence_status).

Free-text ``rationale`` and the generic ``hatch_metadata`` blob let an unlock ship with
nothing behind it but a plausible-sounding sentence. These columns make the citation a
first-class, queryable part of the record instead of prose a curator might have skipped
— see MarketForge's "alternative routes" design: "a route the platform inferred is not
a route."

Idempotent (ADD COLUMN IF NOT EXISTS), same pattern as 0004_escape_hatches.py, which
created the table this follows.

Revision ID: 0007_escape_hatch_provenance
Revises: 0006_showcase_cache
Create Date: 2026-09-06
"""

from __future__ import annotations

from alembic import op

revision = "0007_escape_hatch_provenance"
down_revision = "0006_showcase_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE escape_hatches ADD COLUMN IF NOT EXISTS granting_authority TEXT;")
    op.execute("ALTER TABLE escape_hatches ADD COLUMN IF NOT EXISTS edition TEXT;")
    op.execute(
        "ALTER TABLE escape_hatches ADD COLUMN IF NOT EXISTS evidence_status TEXT "
        "NOT NULL DEFAULT 'unconfirmed';"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE escape_hatches DROP COLUMN IF EXISTS evidence_status;")
    op.execute("ALTER TABLE escape_hatches DROP COLUMN IF EXISTS edition;")
    op.execute("ALTER TABLE escape_hatches DROP COLUMN IF EXISTS granting_authority;")
