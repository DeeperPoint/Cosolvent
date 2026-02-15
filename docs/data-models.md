# Data Models

Cosolvent uses Postgres as the persistence layer.

## Storage Pattern

Current runtime keeps operational entities in shared JSONB-backed tables with a common shape:

- `id` (UUID PK)
- `data` (JSONB payload)
- `created_at`
- `updated_at`

This applies to core operational tables like:

- `users`
- `sessions`
- `profiles`
- `drafts`
- `applications`
- `conversations`
- `messages`
- `notifications`
- `files`
- `private_assets`
- `ai_documents`
- `ai_prompts`
- `ai_llm_settings`
- `ai_chat_threads`
- `ai_chat_messages`

## Vector Tables

Dedicated relational/vector tables:

- `ai_document_chunks` (`embedding vector(1536)`)
- `profile_vectors` (`embedding vector(1536)`)

Indexes include pgvector ANN indexes and trigram support for fallback text search.

## Generated Marketplace Metadata Tables

Generated migration (`alembic/versions/auto_marketplace_*.py`) creates/updates:

1. `marketplace_roles`
2. `marketplace_role_permissions`
3. `marketplace_onboarding_rules`
4. `marketplace_communication_rules`
5. `marketplace_profile_field_defs`
6. `marketplace_builds`

These tables are derived from `marketplace.yaml` and seedable/idempotent per `spec_hash`.

## IDs and API Contract

- IDs are UUID-backed in Postgres.
- API responses keep IDs as opaque strings (`id`).
- Existing endpoint paths remain stable; generated role aliases are additive.

## Session Expiry Note

Mongo TTL behavior is replaced by explicit expiry checks in auth/session flows and index support on session expiry fields.
