# Modules

Each module in `app/modules/` follows a consistent layered pattern: **router** (HTTP) → **service** (logic) → **repository** (database). Schemas define request/response models.

## Auth (`app/modules/auth/`)

Handles user registration, login, sessions, and admin bootstrap.

**Key behavior:**
- Sessions stored in Redis with configurable TTL
- HTTP-only cookies prevent XSS token theft
- Bootstrap endpoint creates the first admin (fails if one exists)
- Passwords hashed with bcrypt

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`

---

## Profiles (`app/modules/profiles/`)

Manages the full profile lifecycle: registration → draft → submit → approval → active profile.

**Key behavior:**
- Profiles double as marketplace listings (no separate listing entity)
- Draft system lets users save progress before submitting
- Schema engine validates fields against the marketplace config
- Completeness computed from required fields
- AI can generate profile content from uploaded documents
- Visibility engine filters fields based on viewer tier

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `ai_generation.py`, `ai_extraction.py`

---

## Files (`app/modules/files/`)

File upload, download, and management with S3 storage.

**Key behavior:**
- Files stored in AWS S3, metadata in MongoDB
- Three privacy levels: `public`, `protected`, `private`
- Files can be associated with a profile
- Owner-only deletion

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `storage.py`

---

## Communication (`app/modules/communication/`)

Conversations, messages, and real-time WebSocket messaging.

**Key behavior:**
- Conversation initiation follows permission engine rules
- Request/approval flow when `requires_approval: true`
- WebSocket connection per conversation for real-time updates
- Message edit and delete with WebSocket broadcast
- Private asset sharing within conversations
- Content types: text, image, video, audio, file

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `websocket.py`

**WebSocket protocol:**
1. Connect to `ws:///api/ws/{conversation_id}`
2. Send auth message: `{"type": "auth", "token": "session_token"}`
3. Send messages: `{"type": "message", "content": "..."}`
4. Server broadcasts to all connected participants

---

## Discovery (`app/modules/discovery/`)

Search and discovery combining keyword matching with vector similarity.

**Key behavior:**
- Searches respect `searchable_types` and `visible_in_search` config
- Filter fields defined in marketplace config
- Vector search via Pinecone (when enabled)
- Results filtered by viewer visibility tier
- Profiles indexed in background worker

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `vector_service.py`, `indexer.py`

---

## Notifications (`app/modules/notifications/`)

User notification system.

**Key behavior:**
- Notifications created by background workers on events
- Events: conversation request, message received, profile approved/rejected
- Read/unread tracking

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`

---

## AI (`app/modules/ai/`)

RAG query pipeline, document knowledge base, and LLM configuration.

**Key behavior:**
- RAG: retrieve relevant document chunks → inject as context → generate LLM answer
- Threaded conversations with history
- Follow-up question generation
- Document ingestion with chunking and embedding
- Configurable LLM provider, model, temperature, max_tokens
- Editable prompt templates stored in MongoDB

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`, `llm_client.py`, `prompt_manager.py`, `document_processor.py`

---

## Admin (`app/modules/admin/`)

Complete operations console for marketplace management.

**Key behavior:**
- All endpoints require `admin` role
- Dashboard with aggregate stats
- User management: list, view, role change, deactivate/activate
- Application approval/rejection workflow
- Profile override: view any profile fully, change status
- Conversation oversight: browse and read any conversation
- AI/LLM management: models, settings, prompts, documents
- FAQ CRUD with sort ordering and active/inactive status
- Admin AI endpoints mirror `/api/ai/*` under `/api/admin/ai/*` for a unified admin namespace

**Files:** `router.py`, `service.py`, `schemas.py`, `repository.py`
