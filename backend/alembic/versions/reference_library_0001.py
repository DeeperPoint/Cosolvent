"""Reference library (Knowledge Slot) tables.

Adds the sponsor-curated domain-knowledge store, kept separate from the
participant-document store. Two-table design: reference_documents (parent,
document-level + provenance metadata) and reference_chunks (searchable text +
embedding + controlled-vocabulary metadata). Natural keys (doc_key, chunk_id)
come from the KnowledgeSlot pipeline so ingestion is idempotent.

Revision ID: reference_library_0001
Revises: mkt_5ed8adda2d87
Create Date: 2026-06-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "reference_library_0001"
down_revision = "mkt_5ed8adda2d87"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "reference_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doc_key", sa.Text(), nullable=False),
        sa.Column("vertical", sa.Text(), nullable=False, server_default="default"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_document", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("doc_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("doc_key", name="uq_reference_documents_doc_key"),
    )
    op.create_index("ix_reference_documents_vertical", "reference_documents", ["vertical"])

    op.create_table(
        "reference_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contextual_content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["document_id"], ["reference_documents.id"],
            name="fk_reference_chunks_document_id", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("chunk_id", name="uq_reference_chunks_chunk_id"),
    )
    op.create_index("ix_reference_chunks_document_id", "reference_chunks", ["document_id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_chunks_metadata_gin "
        "ON reference_chunks USING gin (chunk_metadata jsonb_path_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_chunks_embedding "
        "ON reference_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("ix_reference_chunks_embedding", table_name="reference_chunks")
    op.drop_index("ix_reference_chunks_metadata_gin", table_name="reference_chunks")
    op.drop_index("ix_reference_chunks_document_id", table_name="reference_chunks")
    op.drop_table("reference_chunks")
    op.drop_index("ix_reference_documents_vertical", table_name="reference_documents")
    op.drop_table("reference_documents")
