<!-- Copyright © 2026 Mustafa Uzumeri. All rights reserved. -->

# Cosolvent — Config-Driven Marketplace Engine

An open-source marketplace engine for launching platforms in thin markets. From a single `marketplace.yaml`, Cosolvent generates a policy-aware **FastAPI backend runtime** *and* a **participant-facing Next.js frontend scaffold** — plus a browser-based operator setup wizard and admin API. You go from market definition to a bootable, end-to-end marketplace in days, not quarters.

## The Problem

Most marketplace platforms assume thick markets — many buyers, many sellers, frequent transactions. Thin markets are different:

- the right participants exist, but finding each other is hard,
- trust signals are scattered and unverifiable,
- onboarding is inconsistent across participant types,
- every transaction is high-stakes and structurally complex,
- teams spend months wiring basic flows before learning if the market works.

Cosolvent shortens that path. You should be able to go from idea to a usable, policy-aware marketplace runtime in days, not quarters.

## What Cosolvent Provides Today

Cosolvent is a monorepo: a Python/FastAPI backend and a Python **frontend compiler** that emits a Next.js application. Both read the same `marketplace.yaml`.

| Module | Capability |
|---|---|
| **YAML Compiler (backend)** | Deterministic config → artifacts pipeline: normalize → hash → render → write → manifest. Generates role-alias REST routers, enums, policy matrix, profile models, an OpenAPI spec, and an Alembic migration. Drift detection (`compile --check`), managed output zones, SHA-256 spec hashing. |
| **Frontend Compiler** | Generates a complete Next.js 15 / React 19 / Tailwind / shadcn app from the OpenAPI spec + `marketplace.yaml` — typed API clients, React Query hooks, auth/dashboard/search/profile/conversation pages, role-aware navigation. A customizable scaffold, not a locked black box. |
| **Config Generator** | `gen-config` scaffolds a `marketplace.yaml` from a domain schema; `build-from-docs` seeds a starter config. |
| **Dynamic Profiles** | Runtime Pydantic models generated per participant type from config; completeness scoring and onboarding gates. |
| **Three-Tier Visibility** | `public` / `protected` / `private` per field, enforced by viewer context and ownership. |
| **Participant Roles** | Supply, demand, facilitator — config-driven types (up to 8), each with its own permission set. |
| **AI Onboarding** | LLM field extraction from uploaded documents (text and images) + profile-summary generation. |
| **Semantic Search & Matching** | pgvector cosine search with metadata/field filtering; `hybrid` and `rag_strict` modes; owner-only profile-to-profile **suggested matches** (blended vector + field-overlap score). |
| **Multi-Provider AI** | Provider-agnostic LLM + embedding layer for **OpenAI, OpenRouter, and Google Gemini**, with dynamic model fetching, key validation, and DB-backed prompt management. |
| **Reference Library (CommonContext)** | Sponsor-curated domain knowledge, separate from participant docs: metadata-filtered retrieval and grounded domain Q&A **with citations** and unanswered-question ("gap") capture. |
| **Admin Oversight** | Backend admin API: dashboard, user management, application approval, AI/provider/prompt management, document oversight, FAQ. |
| **Communication** | Conversations with lifecycle management, messaging, WebSocket, in-thread asset sharing. |
| **Permissions** | Config-driven permission checks, conversation-initiation rights, onboarding gates. |
| **Document Processing** | Chunking, embedding, and indexing via ARQ background workers. |
| **File Management** | S3 backend, public/private privacy, presigned URLs, configurable size limits. |
| **Demo Seeding** | `seed_synthetic_poc.py` populates a running market with schema-conforming synthetic participants (tagged for clean teardown) — a stand-in for a ClientSynth digital-twin import. |
| **Deployment** | Docker Compose, Makefile, health checks, graceful shutdown, Redis-optional startup. |
| **Setup UI** | CLI wizard + browser-based setup panel with presets, validation, and live YAML preview. |

## Where AI Helps

AI is useful when it reduces operator and user effort:

- better profile understanding through document extraction (text and images),
- better retrieval and discovery through semantic search and matching,
- faster onboarding through automated field population,
- grounded domain answers through the curated reference library,
- clearer communication support through prompt-managed interactions.

AI is not a replacement for business rules. Market logic comes from explicit configuration and deterministic generation.

## Scope and Vertical Boundaries

Cosolvent provides the foundational matching engine for thin markets, but it is deliberately unopinionated about the specific business conducted over it. The generated frontend is a **starting scaffold** — production UX, branding, and domain execution remain the sponsor's.

**What Cosolvent Handles:**
- AI document extraction and indexing
- Semantic vector matching and suggested matches
- Curated domain knowledge and grounded Q&A
- Baseline role and permission framing
- A generated backend runtime and a starter participant frontend

**What it Defers (The Proprietary/Vertical Layer):**
- **Production Frontend & Branding:** Polished, branded participant experiences beyond the generated scaffold.
- **Domain Ontology:** The specific rules and criteria (defined by the sponsor in `marketplace.yaml`).
- **Trust & Verification:** Validating credentials, mediating disputes, and ensuring real-world safety.
- **Business Add-Ons:** Payments, escrow, monetization engines, digital-twin simulations (e.g., MarketForge & ClientSynth), and physical logistics.

This boundary keeps the open-source engine lightweight and generalizable, while the market sponsor retains ownership of and liability for their market's UX and revenue generation.

## Architecture

```
marketplace.yaml
       │
       ├──────────────────────────────┐
       ▼                              ▼
  Backend Compiler              Frontend Compiler
  (deterministic)               (reads OpenAPI + YAML)
       │                              │
       ├── role-alias routers         ├── typed API clients
       ├── enums, policy matrix       ├── React Query hooks
       ├── profile models             ├── auth / dashboard / search
       ├── OpenAPI spec  ─────────────┘   profile / conversation pages
       ├── Alembic migration          └── role-aware navigation
       └── spec hash + drift check

Cosolvent/
├── backend/
│   ├── app/
│   │   ├── compiler/     Config → artifact pipeline
│   │   ├── core/         Database, settings, config, dependencies
│   │   ├── engine/       Schema, visibility, permission engines
│   │   ├── modules/
│   │   │   ├── admin/          Dashboard & oversight API
│   │   │   ├── ai/             LLM/embedding clients, RAG, providers, prompts
│   │   │   ├── auth/           Cookie-session authentication
│   │   │   ├── communication/  Messaging & WebSocket
│   │   │   ├── discovery/      Search, vector service, suggested matches
│   │   │   ├── files/          S3 file management
│   │   │   ├── knowledge/      Reference library (CommonContext) retrieval
│   │   │   ├── notifications/  Notification plumbing
│   │   │   ├── profiles/       Profile CRUD, AI extraction/generation
│   │   │   └── setup/          Onboarding wizard & setup panel
│   │   ├── generated/    Compiled backend artifacts (do not hand-edit)
│   │   └── workers/      ARQ background jobs (indexing, email)
│   ├── alembic/          DB migrations
│   └── cli/              wizard, validate, compile, load-references
├── frontend/
│   ├── compiler/         Python generator (OpenAPI + YAML → Next.js)
│   └── src/              Generated Next.js app
├── openapi/              Shared OpenAPI spec (backend emits, frontend reads)
├── marketplace.yaml      Active config (currently "Machinery Trade")
└── Makefile              Root orchestration
```

## Quick Start

```bash
git clone https://github.com/DeeperPoint/Cosolvent.git
cd Cosolvent
cp .env.example .env
make setup-up
make onboarding
```

Open: `http://localhost:18080/onboarding`

Then generate and run the backend:

```bash
make compile
make up
make wait-api
```

Optionally generate the participant frontend:

```bash
make generate-frontend
```

API docs: `http://localhost:18000/docs`

## Daily Workflow

1. Open onboarding UI.
2. Update setup decisions.
3. Validate setup.
4. Generate artifacts (backend, and optionally frontend).
5. Run tests.

Recommended checks:

```bash
make lint
make unit
make compile-check
```

## Generated Artifacts

Generated artifacts (`backend/app/generated/`, `openapi/`, `frontend/src/`, and `auto_marketplace_*` migrations) are build outputs and should not be hand-edited. Regenerate them from config and compiler changes.

## Roadmap

See [`Cosolvent-ROADMAP.md`](Cosolvent-ROADMAP.md) for the full development roadmap, including:

- the current build status and what has shipped,
- extension work needed to reach full whitepaper alignment,
- a phased implementation plan,
- unresolved architectural decisions requiring judgment before proceeding.

## Related Projects

| Project | Description |
|---|---|
| [MarketForge](https://github.com/DeeperPoint/MarketForge) | Market configuration and deployment orchestration |
| [CommonContext](https://github.com/DeeperPoint/CommonContext) | AI-curated reference library for domain knowledge (feeds the reference library) |
| [ClientSynth](https://github.com/DeeperPoint/ClientSynth) | Synthetic participant generation for testing and demos (see the demo-seed POC) |

## Documentation

Start with `docs/README.md` for a quick map. See `WHITEPAPER.md` for the thin-market thesis and `FEATURES.md` for the full implemented-vs-planned feature sheet.

## License

See [`LICENSE`](LICENSE).
