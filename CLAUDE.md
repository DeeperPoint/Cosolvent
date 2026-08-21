# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

Monorepo with separate backend and frontend directories:

```
Cosolvent/
├── backend/                   # Python API + backend compiler
│   ├── app/                   # FastAPI application
│   ├── cli/                   # Backend CLI (compile, validate, wizard)
│   ├── alembic/               # DB migrations
│   ├── tests/                 # Backend tests
│   ├── scripts/               # Utility scripts
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                  # Hand-maintained Next.js app (no codegen)
│   ├── src/
│   │   ├── api/                # Hand-written API client + hooks (was `generated/`; see below)
│   │   ├── app/                 # Pages (App Router)
│   │   ├── components/
│   │   └── lib/                 # participant-schemas.ts: hand-maintained mirror of marketplace.yaml
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml         # Shared compose (orchestrates all services)
├── marketplace.yaml           # Shared config (read by the backend compiler; frontend/src/lib/participant-schemas.ts is kept in sync with it by hand)
├── openapi/                   # Backend-generated OpenAPI spec (reference only — nothing reads it automatically)
├── Makefile                   # Root orchestration
└── .env                       # Shared env vars
```

**No frontend code generator.** There used to be a `frontend/compiler/` (OpenAPI + marketplace.yaml → Next.js) — it was removed because it silently went stale (regenerating it was a separate step nobody remembered to run when the vertical changed). `frontend/src/` is now an ordinary hand-maintained Next.js app: when `marketplace.yaml` changes participant types or fields, update `frontend/src/lib/participant-schemas.ts` and the relevant `frontend/src/api/*.ts` client functions by hand, the same as any other client of the backend API.

## Commands

```bash
# Install dependencies
make install                    # Backend: creates backend/.venv and installs deps
cd frontend && npm install      # Frontend

# Linting & formatting (backend, Ruff + mypy)
make lint                       # Check for lint errors
make lint-fix                   # Auto-fix lint errors
make format                     # Format code
make type-check                 # Run mypy

# Testing
make unit                       # Backend unit tests
make integration                # Integration tests (requires Docker stack)
make test-all                   # lint + unit + integration + e2e

# Single backend test
cd backend && .venv/bin/python -m pytest tests/unit/path/to/test.py::ClassName::test_method -v

# Frontend
cd frontend && npm run dev        # Dev server
cd frontend && npm run build      # Production build / type-check
cd frontend && npm run type-check # tsc --noEmit only

# Dev server (Docker, recommended)
make up                         # Start full stack: Postgres + Redis + API + worker
make setup-up                   # Start onboarding UI only (no DB required)
make down                       # Stop stack
make reset                      # Stop and remove volumes
make logs-api                   # Tail API logs

# Dev server (local, needs Postgres + Redis running externally)
make api                        # uvicorn app.main:app --reload
make worker                     # ARQ task worker

# CLI pipeline
make validate-config            # Validate marketplace.yaml
make compile                    # Generate backend artifacts from marketplace.yaml
make compile-check              # Verify generated artifacts match config
```

**URLs when running:**
- Onboarding UI: `http://localhost:18080/onboarding`
- API: `http://localhost:18000/api/`
- Swagger docs: `http://localhost:18000/docs`

## Architecture

### Overview
Config-driven marketplace builder. A single `marketplace.yaml` defines participant types, profile schemas, discovery rules, and onboarding workflows, compiled into backend runtime artifacts by the backend compiler. The frontend is hand-maintained (see above) — no code is generated from `marketplace.yaml` on the frontend side.
- **Backend compiler** (`backend/app/compiler/`): Generates Python runtime artifacts (role routers, enums, policy matrix)

### Backend Module Layout (`backend/app/modules/`)
Each module follows the same pattern: `router.py` (FastAPI routes) → `service.py` (business logic) → `repository.py` (DB access) → `schemas.py` (Pydantic models).

| Module | Responsibility |
|--------|---------------|
| `auth` | Signup/login/sessions via HttpOnly cookies |
| `profiles` | User profiles driven by marketplace.yaml field schemas; whole-profile prose intake + Loop-1 clarify |
| `discovery` | Vector search + weighted/gated matching |
| `deals` | Deal assembly — story-version chain, acknowledge/annotate/correct, consent, facilitator slots, Deal Brief |
| `knowledge` | Reference library + cited Q&A + curatorial pull-signal/escape-hatch loop |
| `reputation` | Post-handoff counterparty ratings |
| `communication` | Conversations, messages, WebSocket real-time |
| `ai` | RAG queries, document management, LLM/embedding config |
| `files` | S3-based storage with presigned URL generation |
| `population` | Synthetic population import + watermark enforcement |
| `showcase` | Precomputed persona/match/Q&A cache for a zero-cost public demo mode |
| `setup` | Onboarding wizard UI + config validation endpoints |
| `admin` | Admin-only management APIs |

### Database (`backend/app/core/`)
**Hybrid Postgres + pgvector** (no MongoDB despite document-style API):
- `db_schema.py`: All tables use `id` (UUID), `data` (JSONB), `created_at`, `updated_at`
- `database.py`: `DatabaseProxy` wraps SQLAlchemy to expose a Mongo-like interface
- `ai_document_chunks` and `profile_vectors` tables store 1536-dim pgvector embeddings

```python
# Mongo-style queries throughout the codebase
db = get_db()
await db.users.find_one({"email": "..."})
await db.profiles.insert_one({...})
```

Migrations are managed with Alembic (`backend/alembic/versions/`).

### AI / Multi-Provider Abstraction (`backend/app/modules/ai/`)
All providers use the OpenAI SDK with a configurable `base_url`. Settings persist in the `ai_llm_settings` MongoDB collection and support per-use-case overrides.

| File | Role |
|------|------|
| `providers.py` | Registry of supported providers (OpenAI, OpenRouter, Gemini) |
| `client_factory.py` | Creates OpenAI clients with correct `base_url` + API key |
| `llm_client.py` | `generate()` with use-case routing (`rag_query`, `follow_up`) |
| `embedding_client.py` | Embedding model client |
| `settings_migration.py` | Auto-migrates legacy single-model schema on startup |
| `document_processor.py` | Chunks documents → embeds → stores in pgvector |

### Config & Startup
- `backend/app/core/config.py`: Pydantic `BaseSettings` loaded from `.env`
- `backend/app/core/marketplace_config.py`: Parses and validates `marketplace.yaml`
- `backend/app/main.py` startup: connects DB, connects Redis, runs `migrate_llm_settings()`

### Backend CLI Compiler (`backend/cli/`)
```bash
cd backend
python -m cli wizard     # Interactive config builder
python -m cli validate   # Validate marketplace.yaml
python -m cli compile    # Generate app/generated/role_alias_router.py and other artifacts
```
Generated artifacts in `backend/app/generated/` must be committed alongside config changes.

### Frontend API Client (`frontend/src/api/`)
Hand-maintained, not generated. `client.ts` (fetch wrapper), `types.ts` (shared request/response shapes), and one file per backend module (`deals.ts`, `admin.ts`, `reputation.ts`, `showcase.ts`, …) with a thin `use-*.ts` hook alongside each. When a backend route changes, edit the matching file directly — there is no build step to re-run.

### Frontend Setup UI (`backend/app/modules/setup/ui/`)
Vanilla JS setup wizard. Key files:
- `main.js`: State machine, step navigation, form handling — the entire wizard logic
- `steps.js`: Step definitions
- `state-utils.js`: Config helpers (clone, defaults, slug management)
- `panel_v3.html` + `onboarding-v3.css`: Active UI (v2 files are legacy)

### Auth
- Session token in HttpOnly `session_token` cookie
- `get_current_user` dependency validates against DB on every request
- `require_admin` dependency for admin-only routes

### Background Jobs (`backend/app/workers/`)
ARQ (Redis-backed) task queue. Worker started with `make worker`. Used for email delivery, document embedding, profile re-indexing.

## Test Structure
```
backend/tests/
├── conftest.py          # Shared fixtures
├── test_config/         # YAML fixtures (agriculture.yaml, talent.yaml, minimal.yaml)
├── unit/                # Fast, isolated — run with make unit
├── integration/         # Requires running stack — run with make integration
└── e2e/                 # Full-stack tests — run with make e2e

```

Async tests use `asyncio_mode = "auto"`. Integration/e2e tests are gated by markers and env vars (`RUN_INTEGRATION=1`, `RUN_E2E=1`).
