"""Bring the reference_library table under migration management.

The Knowledge Slot's ``reference_library`` table was previously created only by
the startup ``metadata.create_all`` and had no migration, so ``alembic upgrade
head`` built an incomplete schema and the table's shape could never evolve via
ALTERs. This creates it explicitly and adds the pgvector ANN index that
``create_all`` does not build.

Idempotent on purpose: many existing databases already created this table
informally via ``create_all``, so every statement is IF NOT EXISTS and must
no-op there rather than error.

Revision ID: reference_library_table_0001
Revises: merge_heads_0001
Create Date: 2026-07-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "reference_library_table_0001"
down_revision = "merge_heads_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_library (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_doc_id UUID NOT NULL,
            vertical TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            reference_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_reference_library_doc_chunk UNIQUE (source_doc_id, chunk_text)
        )
        """
    )
    # ANN index for cosine similarity search (search_reference_library ranks by
    # cosine distance). HNSW gives fast approximate search without a training
    # step; create_all never builds this, so search would otherwise scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_library_embedding_hnsw "
        "ON reference_library USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reference_library_embedding_hnsw")
    op.execute("DROP TABLE IF EXISTS reference_library")
