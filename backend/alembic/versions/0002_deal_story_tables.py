"""Deal-assembly story-progression tables (GAP-4/5/6).

Backfills the ``deals`` document table (added after 0001 via runtime create_all) and adds
the three event-sourced collections the Story Progression System introduces:
``story_versions`` (immutable composed versions), ``version_responses`` (acknowledge /
annotate / correct — the source of truth), and ``consent_records`` (disclosure / audience
consents).

Idempotent (CREATE TABLE IF NOT EXISTS) so it coexists cleanly with the runtime
``metadata.create_all`` path used in development. Chained to the stable base 0001 rather than
the compiler-generated ``mkt_*`` branch, so ``alembic upgrade 0002_deal_story_tables`` walks a
clean 0001 → 0002 path.

Revision ID: 0002_deal_story_tables
Revises: 0001_postgres_pgvector
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op

revision = "0002_deal_story_tables"
down_revision = "0001_postgres_pgvector"
branch_labels = None
depends_on = None

_DOC_TABLES = ["deals", "story_versions", "version_responses", "consent_records"]


def _create_doc_table(name: str) -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {name} (
            id UUID PRIMARY KEY,
            data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    # GIN index over the JSONB payload — supports the Mongo-style field queries the
    # DatabaseProxy issues (e.g. version_responses by deal_id / version_id).
    op.execute(f"CREATE INDEX IF NOT EXISTS ix_{name}_data ON {name} USING GIN (data)")


def upgrade() -> None:
    for name in _DOC_TABLES:
        _create_doc_table(name)


def downgrade() -> None:
    # Drop only the story-chain tables; leave ``deals`` (it predates this migration and may
    # hold records created via the create_all path).
    for name in ["consent_records", "version_responses", "story_versions"]:
        op.execute(f"DROP TABLE IF EXISTS {name}")
