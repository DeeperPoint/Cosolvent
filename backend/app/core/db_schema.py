"""Database schema definitions for Postgres + pgvector."""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

DOCUMENT_COLLECTIONS = [
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
    # Temporary compatibility table while services are migrated.
    "ai_chat_history",
]


def _doc_table(name: str) -> Table:
    return Table(
        name,
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("data", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    )


DOC_TABLES: dict[str, Table] = {name: _doc_table(name) for name in DOCUMENT_COLLECTIONS}

ai_document_chunks = Table(
    "ai_document_chunks",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("ai_documents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("chunk_index", Integer, nullable=False),
    Column("chunk_text", Text, nullable=False),
    Column("embedding", Vector(1536), nullable=False),
    Column("chunk_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    UniqueConstraint("document_id", "chunk_index", name="uq_ai_document_chunks_document_chunk"),
)

profile_vectors = Table(
    "profile_vectors",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column(
        "profile_id",
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("embedding", Vector(1536), nullable=False),
    Column("vector_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)

# ── Knowledge Slot / Reference Library ────────────────────────────────────────
# Sponsor-curated domain knowledge, kept deliberately separate from the
# participant-document store (ai_documents / ai_document_chunks). A two-table
# design mirrors that pattern: a parent document row carries document-level,
# provenance, and versioning metadata; each chunk row carries the searchable
# text + embedding + controlled-vocabulary metadata produced by KnowledgeSlot.
#
# Natural keys (doc_key, chunk_id) come from the upstream KnowledgeSlot pipeline
# so ingestion is idempotent: re-loading regenerated content upserts in place
# rather than duplicating rows.

REFERENCE_EMBEDDING_DIM = 1536  # text-embedding-3-small; must match Cosolvent's other vector tables.

reference_documents = Table(
    "reference_documents",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    # Stable natural key from the curation pipeline (e.g. the document stem "27_2025").
    Column("doc_key", Text, nullable=False, unique=True),
    Column("vertical", Text, nullable=False, server_default=text("'default'")),
    Column("title", Text, nullable=True),
    Column("source_document", Text, nullable=True),
    Column("source_url", Text, nullable=True),
    # Document-level metadata + provenance (doc_type, standard/standard_body,
    # jurisdiction, version, fetched_at, issuing_organization, ...).
    Column("doc_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)

reference_chunks = Table(
    "reference_chunks",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("reference_documents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Natural key from the pipeline (e.g. "27_2025_0"); drives idempotent upsert.
    Column("chunk_id", Text, nullable=False, unique=True),
    Column("content", Text, nullable=False),
    # Heading-prefixed text that is actually embedded ("[doc] H1 > H2 > body").
    Column("contextual_content", Text, nullable=False),
    Column("embedding", Vector(REFERENCE_EMBEDDING_DIM), nullable=False),
    # Chunk-level controlled-vocabulary metadata (doc_type, standard, jurisdiction, topic, ...).
    Column("chunk_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)


def table_for_collection(name: str) -> Table:
    table = DOC_TABLES.get(name)
    if table is None:
        raise KeyError(f"Unknown collection: {name}")
    return table
