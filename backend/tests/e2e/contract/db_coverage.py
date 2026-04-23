"""Database table coverage helpers.

Used by the full-stack lifecycle test (``test_e2e_full_lifecycle``) to
assert that every table meant to be exercised by the public API is
actually populated after the flow completes — i.e. the API really
touches the DB, not just the in-memory session.

Tables are split into two buckets:

* ``REQUIRED_TABLES`` — must have ≥ 1 row after the lifecycle run.
  These are filled by public HTTP routes (users, profiles, messages,
  notifications, faqs, …).

* ``OPTIONAL_TABLES`` — populated only under specific environments
  (real LLM keys, S3-backed private assets, legacy collections). The
  suite reports on them but doesn't fail if empty.
"""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.db_schema import DOCUMENT_COLLECTIONS

REQUIRED_TABLES: tuple[str, ...] = (
    "users",
    "sessions",
    "profiles",
    "drafts",
    "applications",
    "files",
    "conversations",
    "messages",
    "notifications",
    "faqs",
    "ai_documents",
    "ai_prompts",
    "ai_llm_settings",
)

# Tables that exist in the schema but are only populated under
# environment-specific conditions (real LLM, legacy data, unexposed
# features). The lifecycle test reports but does not assert on these.
OPTIONAL_TABLES: tuple[str, ...] = (
    "conversation_participants",  # superseded by conversations.participants JSONB
    "private_assets",             # requires explicit S3 + share-assets flow
    "ai_chat_history",            # legacy compatibility
    "ai_chat_threads",            # populated only if LLM query succeeds
    "ai_chat_messages",           # populated only if LLM query succeeds
)

# Sanity — everything above must be a known collection.
_ALL_KNOWN = set(DOCUMENT_COLLECTIONS)
for _t in REQUIRED_TABLES + OPTIONAL_TABLES:
    assert _t in _ALL_KNOWN, f"{_t} is not in DOCUMENT_COLLECTIONS"


def _resolve_dsn() -> str:
    """Pick the DSN to connect to: explicit env override wins, then app settings."""

    dsn = os.getenv("POSTGRES_DSN") or settings.postgres_dsn or ""
    if not dsn:
        raise RuntimeError(
            "POSTGRES_DSN is not set — cannot connect to the test database."
        )
    return dsn


async def table_counts(tables: tuple[str, ...]) -> dict[str, int]:
    """Return ``{table_name: row_count}``.

    Creates a fresh async engine per call so the query is always bound to
    the current event loop (the app-level engine may be attached to a loop
    from a prior test).
    """

    engine = create_async_engine(_resolve_dsn(), future=True, pool_pre_ping=True)
    try:
        counts: dict[str, int] = {}
        async with engine.connect() as conn:
            for name in tables:
                row = await conn.execute(text(f"SELECT COUNT(*) FROM {name}"))
                counts[name] = int(row.scalar_one())
        return counts
    finally:
        await engine.dispose()


async def assert_required_tables_populated() -> dict[str, int]:
    counts = await table_counts(REQUIRED_TABLES)
    missing = [t for t, n in counts.items() if n == 0]
    if missing:
        raise AssertionError(
            "Required tables are empty after full lifecycle run: "
            + ", ".join(missing)
            + f". Counts: {counts}"
        )
    return counts


async def all_counts() -> dict[str, int]:
    return await table_counts(REQUIRED_TABLES + OPTIONAL_TABLES)
