# Data Models

Cosolvent uses Postgres with a JSONB-backed document model for operational entities and dedicated relational tables for vector data.

## Storage Pattern

Operational entities share a common table structure:

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data       JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

All business fields live inside `data`. The database layer (`app/core/database.py`) exposes a MongoDB-compatible API over these tables:

```python
await db.insert_one("users", {"email": "...", "role": "user"})
await db.find_one("users", {"email": "admin@example.com"})
await db.update_one("users", {"_id": user_id}, {"$set": {"role": "admin"}})
```

IDs are UUIDs in Postgres but exposed as `"_id"` strings in the internal document API (MongoDB compatibility). API responses expose them as `"id"`.

---

## Operational Tables

### `users`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `email` | string | Unique. Indexed. |
| `password_hash` | string | bcrypt hash. Never returned in API responses. |
| `role` | `"user"` \| `"admin"` | Platform role. |
| `participant_type` | string | Participant type slug (e.g. `"producer"`). Set on registration. |
| `is_active` | bool | Deactivated users are denied on all authenticated requests. |
| `has_onboarded` | bool | Whether the user has completed onboarding. |

### `sessions`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `token` | string | Unique session token. Indexed. |
| `user_id` | string | Reference to `users._id`. |
| `expires_at` | ISO datetime | Session expiry. Indexed. |

### `profiles`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `user_id` | string | Profile owner. |
| `participant_type` | string | Type slug. |
| `status` | `"draft"` \| `"pending"` \| `"active"` \| `"rejected"` \| `"suspended"` | Profile lifecycle state. |
| `fields` | object | Profile field values. Validated against schema engine on write. |
| `completeness` | int (0–100) | Computed from required fields. |
| `ai_profile` | object \| null | AI-generated profile draft (pending admin approval). |

### `drafts`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `user_id` | string | One draft per user (unique index). |
| `participant_type` | string | Type slug. |
| `status` | string | Draft state. |
| `fields` | object | In-progress field values. |

### `applications`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `user_id` | string | Applicant. |
| `participant_type` | string | Type slug. |
| `status` | `"pending"` \| `"approved"` \| `"rejected"` | Approval state. Indexed. |
| `submitted_fields` | object | Snapshot of field values at submission time. |
| `admin_feedback` | string \| null | Rejection reason from admin. |

### `files`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `user_id` | string | Uploader. |
| `profile_owner_id` | string \| null | Associated profile. |
| `filename` | string | Original filename. |
| `s3_key` | string | S3 object key. |
| `privacy` | `"public"` \| `"protected"` \| `"private"` | Access level. |
| `status` | `"active"` \| `"deleted"` | Soft delete state. |

### `private_assets`

Files shared within conversations.

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `file_id` | string | Reference to `files._id`. |
| `asset_type` | string | Asset category. |
| `metadata` | object | Additional metadata. |

### `conversations`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `participants` | list[string] | User IDs of all participants. |
| `status` | `"pending"` \| `"active"` \| `"rejected"` \| `"closed"` | Conversation state. |
| `initiator_id` | string | User who started the conversation. |

### `conversation_participants`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `conversation_id` | string | Reference to conversation. |
| `user_id` | string | Participant. |
| `role` | `"initiator"` \| `"receiver"` | Participant role in this conversation. |

### `messages`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `conversation_id` | string | Parent conversation. Indexed. |
| `sender_id` | string | Message author. |
| `body` | string | Message content. |
| `message_type` | `"text"` \| `"image"` \| `"video"` \| `"audio"` \| `"file"` | Content type. |

### `notifications`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `user_id` | string | Recipient. Indexed with `is_read`. |
| `type` | string | Event type (e.g. `"conversation_request"`, `"profile_approved"`). |
| `data` | object | Event-specific payload. |
| `is_read` | bool | Read/unread state. |

### `faqs`

| Field in `data` | Type | Description |
|----------------|------|-------------|
| `question` | string | FAQ question text. |
| `answer` | string | Answer text. |
| `category` | string \| null | Grouping category. |
| `is_active` | bool | Visible to users. |
| `sort_order` | int | Display ordering. |

### AI Tables

| Table | Key fields in `data` |
|-------|---------------------|
| `ai_documents` | `filename`, `status` (`processing`/`indexed`/`failed`), `chunk_count`, `user_id` |
| `ai_prompts` | `intent` (unique indexed), `template`, `is_active` |
| `ai_llm_settings` | `provider`, `model`, `temperature`, `max_tokens` (single-row settings document) |
| `ai_chat_threads` | `user_id`, `profile_id`, `title` |
| `ai_chat_messages` | `thread_id`, `role` (`user`/`assistant`), `content` |
| `ai_chat_history` | `thread_id`, `messages` (compatibility) |

---

## Vector Tables

Dedicated relational tables for pgvector embeddings (not using the JSONB pattern).

### `ai_document_chunks`

Stores chunked document embeddings for RAG retrieval.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Chunk identifier |
| `document_id` | UUID (FK → `ai_documents`, CASCADE) | Parent document |
| `chunk_index` | integer | Position within document |
| `chunk_text` | text | Raw chunk content |
| `embedding` | vector(1536) | Embedding vector |
| `chunk_metadata` | JSONB | Additional metadata |
| `created_at` | timestamptz | — |

**Indexes:** IVFFlat ANN index on `embedding`, unique constraint on `(document_id, chunk_index)`.

> **Note:** Embedding dimensions depend on provider. OpenAI `text-embedding-3-small` = 1536, Gemini `text-embedding-004` = 768. The schema uses 1536; changing providers may require re-indexing.

### `profile_vectors`

Stores profile embeddings for discovery search.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Vector record identifier |
| `profile_id` | UUID (FK → `profiles`, unique, CASCADE) | One-to-one with profile |
| `embedding` | vector(1536) | Embedding vector |
| `vector_metadata` | JSONB | Searchable metadata (participant type, status) |
| `created_at` | timestamptz | — |
| `updated_at` | timestamptz | — |

**Indexes:** IVFFlat ANN index on `embedding`, GIN index on `vector_metadata`.

---

## Generated Marketplace Metadata Tables

The compiler generates an Alembic migration that creates and idempotently seeds these tables from `marketplace.yaml`:

| Table | Purpose |
|-------|---------|
| `marketplace_roles` | Role definitions (name, slug, role type) |
| `marketplace_role_permissions` | Permission flags per role |
| `marketplace_onboarding_rules` | Onboarding requirements per participant type |
| `marketplace_communication_rules` | Who can initiate conversations with whom |
| `marketplace_profile_field_defs` | Profile field schemas per participant type |
| `marketplace_builds` | Build audit trail (spec_hash, generated_at, mode) |

These tables are seeded idempotently per `spec_hash` — running the migration multiple times with the same config is safe.

---

## Indexes

Key indexes created at startup by `app/core/database.py`:

| Index | Table | Purpose |
|-------|-------|---------|
| `uq_users_email` | users | Unique email |
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

---

## See Also
- [Architecture](architecture.md) — data strategy overview
- [Modules](modules.md) — which module owns which tables
- [Workers](workers.md) — async indexing into vector tables
