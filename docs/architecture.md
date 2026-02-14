# Architecture

## Overview

Cosolvent is a configurable, single-tenant marketplace platform. A single YAML configuration file (`marketplace.yaml`) drives all runtime behavior — participant types, profile schemas, permissions, communication rules, discovery settings, and onboarding workflows.

The backend is a FastAPI application backed by MongoDB (via Motor for async operations), Redis (sessions and job queues), Pinecone (vector search), and S3 (file storage).

## Project Structure

```
cosolvent-beta/
├── app/                        # Backend application
│   ├── main.py                 # FastAPI app factory, router registration
│   ├── core/                   # Shared infrastructure
│   │   ├── config.py           # Pydantic settings (env vars)
│   │   ├── marketplace_config.py  # YAML config loader + validation models
│   │   ├── database.py         # Motor MongoDB connection + indexes
│   │   ├── redis.py            # Redis connection
│   │   ├── security.py         # Password hashing
│   │   ├── dependencies.py     # FastAPI DI (auth, permissions, config)
│   │   ├── exceptions.py       # Custom exceptions + handlers
│   │   └── middleware.py       # CORS, logging middleware
│   ├── engine/                 # Config-driven runtime engines
│   │   ├── schema_engine.py    # Dynamic Pydantic model generation
│   │   ├── visibility_engine.py # Field visibility filtering
│   │   └── permission_engine.py # Permission + conversation rule checks
│   ├── modules/                # Feature modules (each: router/service/repo/schemas)
│   │   ├── auth/               # Signup, login, sessions, admin bootstrap
│   │   ├── profiles/           # Drafts, onboarding, profile CRUD, AI generation
│   │   ├── files/              # S3 upload/download, privacy levels
│   │   ├── communication/      # Conversations, messages, WebSocket
│   │   ├── discovery/          # Search, vector search, indexing
│   │   ├── notifications/      # User notifications
│   │   ├── ai/                 # RAG queries, LLM settings, document KB
│   │   └── admin/              # Dashboard, user mgmt, FAQ, oversight
│   └── workers/                # Arq background tasks
│       ├── settings.py         # Worker config + task registry
│       ├── document_indexing.py
│       ├── profile_indexing.py
│       └── email_sender.py
├── cli/                        # CLI wizard & validation
│   ├── __main__.py             # Argparse entry point
│   ├── wizard.py               # 7-step orchestrator
│   ├── validate.py             # Config file validation
│   ├── steps/                  # Individual wizard steps
│   └── presets/                # Pre-built marketplace configs
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── e2e/                    # End-to-end tests
│   └── test_config/            # YAML fixture configs
└── pyproject.toml
```

## Module Pattern

Every feature module follows the same layered pattern:

```
module/
├── router.py       # FastAPI endpoints — input validation, dependency injection
├── service.py      # Business logic — orchestrates repo calls, raises domain errors
├── repository.py   # Database access — raw MongoDB queries
└── schemas.py      # Pydantic request/response models
```

**Flow:** Router → Service → Repository → MongoDB

The router layer handles HTTP concerns (path params, query params, request bodies, auth dependencies). The service layer contains business logic and raises domain exceptions (`NotFoundError`, `ForbiddenError`). The repository layer executes MongoDB operations.

## Engines

Engines are stateless, config-driven components that interpret the marketplace YAML at runtime:

| Engine | Purpose |
|--------|---------|
| `schema_engine` | Generates Pydantic validation models from profile schema config. Caches models per type. |
| `visibility_engine` | Filters profile fields by viewer tier (anonymous → public, authenticated → protected, owner/admin → all). |
| `permission_engine` | Checks participant permissions and conversation initiation rules from config. |

## Authentication & Authorization

- **Sessions:** Token-based, stored in Redis with configurable TTL (default 72h). Delivered via HTTP-only cookies.
- **User roles:** `user` or `admin`. Admins bypass all permission checks.
- **Deactivation guard:** Users with `is_active: false` receive 403 on any authenticated request.
- **Permission checks:** Config-driven via `ParticipantPermissions` on each type.
- **Conversation rules:** Defined per initiator→receiver pair in `communication.conversation_rules`.

## Data Flow

```
marketplace.yaml  ──→  MarketplaceConfig (Pydantic)  ──→  Runtime singleton
                                                            ↓
                                          Engines read config to validate
                                          schemas, filter fields, check
                                          permissions at request time
```

## AI Integration

```
Documents  ──→  Chunking  ──→  Embeddings (OpenAI)  ──→  Pinecone
                                                            ↓
User Query  ──→  Embedding  ──→  Vector Search  ──→  Context
                                                            ↓
Context + Query  ──→  Prompt Template  ──→  LLM  ──→  Answer
```

- **RAG pipeline:** Retrieve relevant chunks from Pinecone, inject as context into LLM prompt.
- **Prompt templates:** Stored in MongoDB, editable via admin API.
- **AI profile generation:** LLM generates profile content from uploaded documents during onboarding.
- **Model configuration:** Provider/model/temperature/max_tokens configurable via admin settings.

## Background Workers

Arq workers process async tasks via Redis queue:

| Task | Trigger |
|------|---------|
| `process_document_task` | Document uploaded to knowledge base |
| `index_profile_task` | Profile created or updated |
| `send_email_task` | Approval notifications, welcome emails |
