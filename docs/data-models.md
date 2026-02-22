# Data Models

Cosolvent uses Postgres as the persistence layer with a JSONB-backed document model for operational entities and dedicated relational tables for vector data.

## Architecture

The database layer (`app/core/database.py`) provides a Mongo-style collection API over Postgres JSONB. This gives document flexibility while retaining Postgres features like transactions, indexes, and pgvector.

## Storage Pattern

Operational entities share a common table structure:

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID (PK) | Unique identifier |
| `data` | JSONB | Full document payload |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last modification timestamp |

All business fields live inside the `data` column. The API layer reads/writes documents using a MongoDB-compatible interface (`find`, `find_one`, `insert_one`, `update_one`, `delete_one`).

## Operational Tables

These tables use the JSONB document pattern described above:

| Table | Module | Key Fields in `data` |
|-------|--------|---------------------|
| `users` | auth | `email`, `password_hash`, `role`, `participant_type`, `is_active`, `has_onboarded` |
| `sessions` | auth | `token`, `user_id`, `expires_at` |
| `profiles` | profiles | `user_id`, `participant_type`, `status`, `fields`, `completeness`, `ai_profile` |
| `drafts` | profiles | `user_id`, `participant_type`, `status`, `fields` |
| `applications` | profiles | `user_id`, `participant_type`, `status`, `submitted_fields`, `admin_feedback` |
| `files` | files | `user_id`, `profile_owner_id`, `filename`, `s3_key`, `privacy`, `status` |
| `private_assets` | files | `file_id`, `asset_type`, `metadata` |
| `conversations` | communication | `participants`, `status`, `initiator_id` |
| `conversation_participants` | communication | `conversation_id`, `user_id`, `role` |
| `messages` | communication | `conversation_id`, `sender_id`, `body`, `message_type` |
| `notifications` | notifications | `user_id`, `type`, `data`, `is_read` |
| `faqs` | admin | `question`, `answer`, `is_active`, `sort_order` |
| `ai_documents` | ai | `filename`, `status`, `chunk_count`, `user_id` |
| `ai_prompts` | ai | `intent`, `template`, `is_active` |
| `ai_llm_settings` | ai | `model`, `temperature`, `max_tokens` |
| `ai_chat_threads` | ai | `user_id`, `profile_id`, `title` |
| `ai_chat_messages` | ai | `thread_id`, `role`, `content` |
| `ai_chat_history` | ai | `thread_id`, `messages` (compatibility) |

## Vector Tables

Dedicated relational tables for pgvector embeddings:

### `ai_document_chunks`

Stores chunked document embeddings for RAG retrieval.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID (PK) | Chunk identifier |
| `document_id` | UUID (FK → `ai_documents`) | Parent document (CASCADE delete) |
| `chunk_index` | Integer | Position within document |
| `chunk_text` | Text | Raw chunk content |
| `embedding` | vector(1536) | OpenAI embedding |
| `chunk_metadata` | JSONB | Additional metadata |
| `created_at` | timestamptz | Creation timestamp |

**Indexes:** IVFFlat ANN index on `embedding`, unique constraint on `(document_id, chunk_index)`.

### `profile_vectors`

Stores profile embeddings for discovery search.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID (PK) | Vector record identifier |
| `profile_id` | UUID (FK → `profiles`, unique) | One-to-one with profile (CASCADE delete) |
| `embedding` | vector(1536) | OpenAI embedding |
| `vector_metadata` | JSONB | Searchable metadata (participant type, status) |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

**Indexes:** IVFFlat ANN index on `embedding`, GIN index on `vector_metadata`.

## Generated Marketplace Metadata Tables

The compiler generates a migration (`alembic/versions/auto_marketplace_*.py`) that creates:

| Table | Purpose |
|-------|---------|
| `marketplace_roles` | Role definitions from config |
| `marketplace_role_permissions` | Permission matrix per role |
| `marketplace_onboarding_rules` | Onboarding requirements per participant type |
| `marketplace_communication_rules` | Who can initiate conversations with whom |
| `marketplace_profile_field_defs` | Profile field schemas per participant type |
| `marketplace_builds` | Build/generation audit trail |

These tables are derived from `marketplace.yaml` and seeded idempotently per `spec_hash`.

## IDs and API Contract

- IDs are UUID-backed in Postgres.
- API responses expose IDs as opaque strings (`"id": "..."`)
- Internal code references `doc["_id"]` (Mongo compatibility) which maps to the `id` UUID column.
- Existing endpoint paths remain stable; generated role aliases are additive.

## Indexes

Key indexes created at startup (`app/core/database.py`):

| Index | Table | Purpose |
|-------|-------|---------|
| `uq_users_email` | users | Unique email constraint |
| `uq_sessions_token` | sessions | Unique session token |
| `uq_drafts_user_id` | drafts | One draft per user |
| `uq_ai_prompts_intent` | ai_prompts | Unique prompt intent |
| `ix_sessions_expires_at` | sessions | Session expiry queries |
| `ix_profiles_type_status` | profiles | Profile type/status filtering |
| `ix_applications_status` | applications | Application status filtering |
| `ix_messages_conversation` | messages | Message lookup by conversation |
| `ix_notifications_user_read` | notifications | Notification queries |
| `ix_profiles_data_trgm` | profiles | Trigram text search fallback |
| `ix_profiles_data_gin` | profiles | GIN containment queries |

## Session Expiry Note

Session expiry is handled by explicit checks in auth/session flows, supported by the `ix_sessions_expires_at` index on the session expiry field.
