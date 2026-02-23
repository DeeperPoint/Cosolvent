# Modules

All domain modules live in `app/modules/`. Each follows the same layered pattern:

```
router.py     ← HTTP layer: route definitions, request parsing, response shaping
service.py    ← Business logic: orchestrates repositories and engines
repository.py ← Database layer: CRUD operations via the collection API
schemas.py    ← Pydantic request/response models
```

---

## Auth (`app/modules/auth/`)

Handles user registration, login, session management, and admin bootstrap.

**Key behavior:**
- Sessions are stored in Redis with configurable TTL (`SESSION_TTL_HOURS`, default 72h)
- `session_token` is delivered as an HTTP-only cookie (prevents XSS token theft)
- Bootstrap endpoint creates the first admin account and fails if one already exists
- Passwords hashed with bcrypt

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`

**Cross-module dependencies:**
- `app/core/dependencies.py` — session verification used by all authenticated endpoints

---

## Profiles (`app/modules/profiles/`)

Manages the full profile lifecycle: registration → draft → submit → approval → active.

**Lifecycle states:**
```
(user registers) → draft → submitted → pending_approval → active
                                                        → rejected → draft
```

**Key behavior:**
- Profiles double as marketplace listings — there is no separate listing entity
- The schema engine validates field values against `marketplace.yaml` on every save
- Completeness is computed from required fields and enforced at submit time
- AI can generate profile content from documents (`ai_generation.py`)
- AI can extract fields from uploaded documents (`ai_extraction.py`)
- The visibility engine filters fields before serving profile responses

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `ai_generation.py`, `ai_extraction.py`

**Cross-module dependencies:**
- `app/engine/schema_engine.py` — field validation, completeness
- `app/engine/visibility_engine.py` — field filtering
- `app/engine/permission_engine.py` — checks `requires_approval`, `requires_onboarding`
- `app/workers/` — profile vector indexing queued after profile updates

---

## Files (`app/modules/files/`)

File upload, download, and management with AWS S3 backing.

**Key behavior:**
- Files are stored in S3; metadata (filename, S3 key, privacy, owner) is stored in the `files` table
- Three privacy levels: `public`, `protected`, `private`
- Files can be associated with a profile (`profile_owner_id`)
- Only the owner can delete a file
- Private files require a presigned S3 URL (TTL controlled by `FILES_PRIVATE_URL_TTL_SECONDS`)

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `storage.py`

---

## Communication (`app/modules/communication/`)

Conversations, messages, and real-time WebSocket messaging.

**Key behavior:**
- Conversation initiation checks the permission engine for a matching `conversation_rule`
- When `requires_approval: true`, the receiver must accept before messaging begins
- WebSocket connection per conversation for real-time updates
- Message edit and delete with WebSocket broadcast to all participants
- Private asset sharing (files) within conversations
- Content types: `text`, `image`, `video`, `audio`, `file`

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `websocket.py`

**WebSocket protocol:**
1. Connect: `ws://host/api/ws/{conversation_id}`
2. Authenticate: `{"type": "auth", "token": "<session_token>"}`
3. Send message: `{"type": "message", "content": "..."}`
4. Ping: `{"type": "ping"}` → server responds with `{"type": "pong"}`
5. Server broadcasts all messages to all connected participants

**Cross-module dependencies:**
- `app/engine/permission_engine.py` — `can_initiate_conversation` check
- `app/modules/notifications/` — notification creation on new messages and requests

---

## Discovery (`app/modules/discovery/`)

Search and discovery combining keyword and vector similarity.

**Key behavior:**
- Respects `searchable_types` and `visible_in_search` from marketplace config
- Filter fields defined in `marketplace.yaml` under `discovery.filter_fields`
- Vector search via pgvector (profile embeddings in `profile_vectors` table)
- Results filtered by viewer visibility tier before returning
- Profile vectors indexed in background worker after profile creation/update

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `vector_service.py`, `indexer.py`

**Cross-module dependencies:**
- `app/engine/visibility_engine.py` — result field filtering
- `app/engine/permission_engine.py` — `can_search` check
- `app/modules/ai/embedding_client.py` — query embedding for vector search
- `app/workers/profile_indexing.py` — background profile vector updates

---

## Notifications (`app/modules/notifications/`)

User notification system.

**Key behavior:**
- Notifications are created by background workers and service calls when events occur
- Events: conversation request received, message received, profile approved/rejected
- Read/unread tracking per user

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`

---

## AI (`app/modules/ai/`)

RAG query pipeline, document knowledge base, LLM configuration, and prompt management.

**Key behavior:**
- RAG flow: retrieve relevant document chunks from pgvector → inject as context → generate LLM answer
- Threaded conversations with message history (stored in `ai_chat_threads` and `ai_chat_messages`)
- Follow-up question generation using the same thread context
- Document ingestion: upload text → chunk → embed → store in `ai_document_chunks`
- Configurable LLM provider, model, temperature, max_tokens stored in `ai_llm_settings`
- Editable prompt templates stored in `ai_prompts` collection

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `llm_client.py`, `prompt_manager.py`, `document_processor.py`, `providers.py`, `embedding_client.py`, `client_factory.py`

**Cross-module dependencies:**
- `app/modules/ai/providers.py` — provider registry
- `app/workers/document_indexing.py` — async chunking and embedding

---

## Admin (`app/modules/admin/`)

Complete operations console for marketplace management.

**Key behavior:**
- All endpoints require `admin` role
- Dashboard returns aggregate stats (users, profiles, conversations, pending applications)
- User management: list, view, role change, deactivate/activate
- Application approval/rejection workflow
- Profile override: view any profile fully (bypasses visibility), change status
- Conversation oversight: browse and read any conversation
- AI/LLM management: provider settings, prompt templates, knowledge base documents
- FAQ CRUD with sort ordering and active/inactive status
- Admin AI endpoints under `/api/admin/ai/*` mirror the public `/api/ai/*` surface

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`

---

## Setup (`app/modules/setup/`)

Onboarding wizard UI and the compilation API. Only active in `setup_app.py`.

**Key behavior:**
- Serves `panel_v2.html` (the wizard SPA) at `/onboarding`
- Serves JS/CSS assets from `app/modules/setup/ui/`
- Config validation, YAML render, save, and compile endpoints
- Preset library (`presets.py`) for template starting points

**Files:** `router.py`, `ui/` (vanilla JS wizard)

**Cross-module dependencies:**
- `app/compiler/` — all generation operations
- `app/core/marketplace_config.py` — config validation

---

## See Also
- [Architecture](architecture.md) — how modules fit together
- [Engines](engines.md) — permission, schema, visibility engines
- [API Reference](api-reference.md) — complete endpoint listing
