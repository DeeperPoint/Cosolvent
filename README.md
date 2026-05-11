<!-- Copyright © 2026 Mustafa Uzumeri. All rights reserved. -->

# Cosolvent — Headless Marketplace Engine

An open-source, headless marketplace engine for launching marketplace platforms in thin markets. Includes a full sponsor admin dashboard; the participant-facing frontend is yours to build — using AI or any stack you choose.

## The Problem

Most marketplace platforms assume thick markets — many buyers, many sellers, frequent transactions. Thin markets are different:

- the right participants exist, but finding each other is hard,
- trust signals are scattered and unverifiable,
- onboarding is inconsistent across participant types,
- every transaction is high-stakes and structurally complex,
- teams spend months wiring basic flows before learning if the market works.

Cosolvent shortens that path. You should be able to go from idea to a usable, policy-aware marketplace runtime in days, not quarters.

## What Cosolvent Provides Today

Cosolvent is a Python/FastAPI backend with working implementations of core marketplace infrastructure:

| Module | Capability |
|---|---|
| **YAML Compiler** | Deterministic config → artifacts pipeline with drift detection, managed output zones, spec hashing |
| **Dynamic Profiles** | Runtime Pydantic models generated from marketplace config; completeness calculation |
| **Three-Tier Visibility** | `public` / `protected` / `private` per field, enforcement by viewer context |
| **Participant Roles** | Supply, demand, facilitator — config-driven participant types |
| **AI Onboarding** | LLM-powered field extraction from documents + profile summary generation |
| **Semantic Search** | pgvector cosine-distance search with metadata filtering, hybrid and RAG modes |
| **Admin Oversight** | Dashboard, user management, application approval, LLM/prompt management, FAQ |
| **Communication** | Conversations with lifecycle management, messaging, WebSocket, asset sharing |
| **Permissions** | Config-driven permission checks, conversation initiation rights, onboarding gates |
| **Document Processing** | Text chunking, embedding, indexing via background workers |
| **File Management** | S3 backend, public/private privacy, presigned URLs |
| **Deployment** | Docker Compose, Makefile, health checks, graceful shutdown, Redis-optional startup |
| **CLI & Setup UI** | 7-step wizard + browser-based setup panel with presets, validation, YAML preview |

## Where AI Helps

AI is useful when it reduces operator and user effort:

- better profile understanding through document extraction,
- better retrieval and discovery through semantic search,
- faster onboarding through automated field population,
- clearer communication support through prompt-managed interactions.

AI is not a replacement for business rules. Market logic comes from explicit configuration and deterministic generation.

## Scope and Vertical Boundaries

Cosolvent provides the foundational matching engine for thin markets, but it is strictly unopinionated about the specific business conducted over it. It deliberately defers domain-specific execution to **market vertical customizations**.

**What Cosolvent Handles:**
- AI document extraction and indexing
- Semantic vector matching
- Multilateral deal architecture
- Baseline role and permission framing

**What it Defers (The Proprietary/Vertical Layer):**
- **Frontend Interfaces:** All user-facing web, mobile, and conversational UIs.
- **Domain Ontology:** The specific rules and criteria (defined by the sponsor in `marketplace.yaml`).
- **Trust & Verification:** Validating credentials, mediating disputes, and ensuring real-world safety.
- **Business Add-Ons:** Payments, escrow, monetization engines, digital twin simulations (e.g., MarketForge & ClientSynth), and physical logistics.

This functional boundary keeps the open-source Cosolvent engine lightweight, generalizable, and scalable, while the market sponsor retains total ownership and liability over their market's UX and revenue generation.

## Architecture

```
marketplace.yaml
       │
       ▼
  YAML Compiler (deterministic)
       │
       ├── Generated schemas, routes, migrations
       ├── Managed output zones
       └── Spec hash + drift detection

  app/
  ├── compiler/     Config → artifact pipeline
  ├── core/         Database, settings, dependencies
  ├── engine/       Schema engine, visibility engine, permission engine
  ├── modules/
  │   ├── admin/          Dashboard & oversight
  │   ├── ai/             LLM client, extraction, generation, RAG, vectors
  │   ├── auth/           Authentication
  │   ├── communication/  Messaging & WebSocket
  │   ├── discovery/      Search & matching
  │   ├── files/          S3 file management
  │   ├── notifications/  Notification plumbing
  │   ├── profiles/       Profile CRUD & schemas
  │   └── setup/          Onboarding wizard & setup panel
  └── workers/      Background job processing (ARQ)
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

Then generate and run:

```bash
make compile
make up
make wait-api
```

API docs: `http://localhost:18000/docs`

## Daily Workflow

1. Open onboarding UI.
2. Update setup decisions.
3. Validate setup.
4. Generate artifacts.
5. Run tests.

Recommended checks:

```bash
make lint
make unit
make compile-check
```

## Generated Artifacts

Generated artifacts are local build outputs and should not be hand-edited. Regenerate from config and compiler changes.

## Roadmap

See [`Cosolvent-ROADMAP.md`](Cosolvent-ROADMAP.md) for the full development roadmap, including:

- extension work needed to reach full whitepaper alignment,
- phased implementation plan (estimated 14–20 weeks to demo-able state),
- unresolved architectural decisions requiring judgment before proceeding.

## Related Projects

| Project | Description |
|---|---|
| [MarketForge](https://github.com/DeeperPoint/MarketForge) | Market configuration and deployment orchestration |
| [CommonContext](https://github.com/DeeperPoint/CommonContext) | AI-curated reference library for domain knowledge |
| [ClientSynth](https://github.com/DeeperPoint/ClientSynth) | Synthetic participant generation for testing and demos |

## Documentation

Start with `docs/README.md` for a quick map.

## License

See [`LICENSE`](LICENSE).
