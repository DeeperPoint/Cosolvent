"""Database schema definitions for Postgres + pgvector."""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    text,
)
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
    "deals",
    # Story Progression System (GAP-4): the deal's witnessed story-version chain.
    # Versions are immutable; responses and consents are the event-sourced source of
    # truth from which milestone/deal state is derived (never a free-standing flag).
    "story_versions",
    "version_responses",
    "consent_records",
    "notifications",
    # Post-handoff bidirectional ratings (roadmap §9.2 reputation system / trust
    # stage 6 "post-transaction evaluation"). One row per (deal, rater, ratee).
    "deal_ratings",
    "faqs",
    # Pre-computed showcase cache (MarketForge Phase 6a "Mode 1"): baked match
    # results and curated knowledge Q&A so a public demo instance never needs a
    # live vector search or LLM call per visitor. One row per (kind, cache_key).
    "showcase_cache",
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


# Knowledge Slot — sponsor-curated reference library (CommonContext output).
# Unlike ai_document_chunks (per-participant uploads), these are vertical-wide
# reference documents (contracts, standards, regulations) loaded by the sponsor and
# queried by the marketplace AI at runtime. See MarketForge ks-to-cosolvent contract.
reference_library = Table(
    "reference_library",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("source_doc_id", UUID(as_uuid=True), nullable=False),
    Column("vertical", Text, nullable=False),
    Column("chunk_text", Text, nullable=False),
    # A real chunk (a whole converted document section, in practice) routinely runs
    # past Postgres's btree row-size limit (~2704 bytes at the default 8KB page size)
    # — indexing chunk_text directly failed on ordinary Wikipedia-length prose the
    # first time this table was loaded with real (non-synthetic-sample) content.
    # Dedup on a fixed-size hash of it instead; server-computed so every writer gets
    # it for free (see knowledge/service.py::normalize_record, which never sets it).
    Column("chunk_text_hash", Text, Computed("md5(chunk_text)", persisted=True)),
    Column("embedding", Vector(1536), nullable=False),
    Column("reference_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    UniqueConstraint("source_doc_id", "chunk_text_hash", name="uq_reference_library_doc_chunk"),
)


# Loop-2 "Pull Signal" (GAP-14): knowledge gaps detected either by wiki-lint (CommonContext
# emits here via gap_signal.py) or at query time when the reference library can't answer well.
# The curation side reads these to decide what knowledge to acquire next.
knowledge_gap_signals = Table(
    "knowledge_gap_signals",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("query", Text, nullable=False),
    Column("topic_needed", Text, nullable=False, server_default=text("''")),
    Column("jurisdiction_needed", Text, nullable=False, server_default=text("''")),
    Column("gap_description", Text, nullable=False, server_default=text("''")),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("status", Text, nullable=False, server_default=text("'open'")),
    Column("vertical", Text, nullable=True),
    Column("filters", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # Why the gap was recorded: "no_matching_chunks" | "model_not_covered" |
    # "answer_without_citation" | "match_gate_blocked". Defaulted so writers that don't
    # classify a reason (e.g. record_gap_signal) still satisfy the NOT NULL constraint.
    Column("reason", Text, nullable=False, server_default=text("''")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)


# Loop-2 escape hatches (GAP-14, payoff half): curator-ingested alternative-compliance
# rules that make a hard match gate *conditional*. When a candidate fails a gate
# (`gate_name`) but satisfies this hatch's `condition` (an alternative predicate on the
# candidate's fields), the matching engine unlocks the gate instead of excluding the
# candidate — the "Match is unlocked!" moment of The Regulatory Escape Hatch.
escape_hatches = Table(
    "escape_hatches",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("vertical", Text, nullable=True),
    # The hard-gate this hatch conditions (matches HardGate.name in the matching config).
    Column("gate_name", Text, nullable=False),
    # Alternative-compliance predicate: {"field": ..., "op": ..., "value": ...}, same
    # shape/semantics as a HardGate. If it passes, the blocked gate is unlocked.
    Column("condition", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # Human-readable "why this unlocks" shown on the match (e.g. "holds CWB W59-002").
    Column("rationale", Text, nullable=False, server_default=text("''")),
    Column("status", Text, nullable=False, server_default=text("'active'")),
    Column("hatch_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)


def table_for_collection(name: str) -> Table:
    table = DOC_TABLES.get(name)
    if table is None:
        raise KeyError(f"Unknown collection: {name}")
    return table
