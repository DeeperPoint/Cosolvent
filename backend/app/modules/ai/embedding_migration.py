"""Vector column dimension migration when embedding provider/dimensions change."""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import session_scope

logger = logging.getLogger("cosolvent.ai.embedding_migration")


async def migrate_embedding_dimensions(new_dimensions: int) -> None:
    """Migrate vector columns to a new dimension size.

    This will:
    1. Drop IVFFlat indexes on embedding columns
    2. Truncate both tables (vectors must be regenerated)
    3. ALTER COLUMN embedding TYPE vector(N)
    4. Recreate indexes
    5. Log that re-indexing is required
    """
    logger.warning(
        "Embedding dimension migration starting: changing to %d dimensions. "
        "All existing vectors will be cleared and must be re-indexed.",
        new_dimensions,
    )

    async with session_scope() as session:
        # Drop indexes (ignore if not exist)
        await session.execute(text(
            "DROP INDEX IF EXISTS ix_ai_document_chunks_embedding"
        ))
        await session.execute(text(
            "DROP INDEX IF EXISTS ix_profile_vectors_embedding"
        ))

        # Truncate tables
        await session.execute(text("TRUNCATE TABLE ai_document_chunks"))
        await session.execute(text("TRUNCATE TABLE profile_vectors"))

        # Alter column types
        await session.execute(text(
            f"ALTER TABLE ai_document_chunks "
            f"ALTER COLUMN embedding TYPE vector({new_dimensions})"
        ))
        await session.execute(text(
            f"ALTER TABLE profile_vectors "
            f"ALTER COLUMN embedding TYPE vector({new_dimensions})"
        ))

        # Recreate indexes
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ai_document_chunks_embedding "
            "ON ai_document_chunks USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        ))
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_profile_vectors_embedding "
            "ON profile_vectors USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        ))

        await session.commit()

    logger.warning(
        "Embedding dimension migration complete (%d dims). "
        "All documents and profiles must be re-indexed.",
        new_dimensions,
    )
