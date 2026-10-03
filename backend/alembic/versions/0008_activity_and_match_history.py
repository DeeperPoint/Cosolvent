"""Activity events and scoring history.

Three document collections:

* ``activity_events`` — append-only record of what happened in the market, read
  as a feed and as the audit trail of one profile.
* ``match_runs`` / ``match_ledger`` — the showcase cache keeps only the latest
  result for a pairing, so these keep the history: one row per precompute run,
  one per pairing scored in it.

Revision ID: 0008_activity_match_history
Revises: merge_heads_0002
Create Date: 2026-10-03
"""

from __future__ import annotations

from alembic import op

revision = "0008_activity_match_history"
down_revision = "merge_heads_0002"
branch_labels = None
depends_on = None

_TABLES = ("activity_events", "match_runs", "match_ledger")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    for table in _TABLES:
        op.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    # Both readers filter on a JSONB field and order by time, so index the two
    # that decide the query plan rather than every key.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activity_events_subject "
        "ON activity_events ((data->>'subject_type'), (data->>'subject_id'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activity_events_created "
        "ON activity_events (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_match_ledger_profile "
        "ON match_ledger ((data->>'participant_type'), (data->>'profile_id'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_match_runs_started "
        "ON match_runs ((data->>'started_at') DESC)"
    )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
