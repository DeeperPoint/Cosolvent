"""Initial Postgres + pgvector schema.

Revision ID: 0001_postgres_pgvector
Revises:
Create Date: 2026-02-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_postgres_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    doc_tables = [
        "users",
        "sessions",
        "profiles",
        "drafts",
        "applications",
        "files",
        "private_assets",
        "conversations",
        "conversation_participants",
        "messages",
        "notifications",
        "faqs",
        "ai_documents",
        "ai_prompts",
        "ai_llm_settings",
        "ai_chat_threads",
        "ai_chat_messages",
        "ai_chat_history",
    ]

    for name in doc_tables:
        op.create_table(
            name,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        )

    op.create_table(
        "ai_document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "profile_vectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "vector_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users ((data->>'email'))")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_token ON sessions ((data->>'token'))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sessions_expires_at ON sessions ((data->>'expires_at'))")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_profiles_type_status ON profiles ((data->>'participant_type'), (data->>'status'))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_applications_status ON applications ((data->>'status'))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages ((data->>'conversation_id'))")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications ((data->>'user_id'), (data->>'is_read'))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_profiles_data_trgm ON profiles USING gin ((data::text) gin_trgm_ops)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_profile_vectors_embedding "
        "ON profile_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_document_chunks_embedding "
        "ON ai_document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("profile_vectors")
    op.drop_table("ai_document_chunks")

    for name in [
        "ai_chat_history",
        "ai_chat_messages",
        "ai_chat_threads",
        "ai_llm_settings",
        "ai_prompts",
        "ai_documents",
        "faqs",
        "notifications",
        "messages",
        "conversation_participants",
        "conversations",
        "private_assets",
        "files",
        "applications",
        "drafts",
        "profiles",
        "sessions",
        "users",
    ]:
        op.drop_table(name)
