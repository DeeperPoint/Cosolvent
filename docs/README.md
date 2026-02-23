# Documentation

Choose your path:

---

## I want to build a marketplace

You are a founder or operator who wants to deploy Cosolvent to run your own marketplace.

| Page | What it covers |
|------|---------------|
| [What Is Cosolvent?](user/index.md) | Platform overview, the thin-market problem, key concepts |
| [Quick Start](user/quick-start.md) | Clone → configure → generate → boot in ~10 minutes |
| [Setup Wizard](user/setup-wizard.md) | Full 8-step wizard walkthrough with every field explained |
| [Marketplace Config Reference](user/marketplace-config.md) | Every `marketplace.yaml` field, type, default, and constraint |
| [Environment Variables](user/environment.md) | Every `.env` variable: required vs. optional, what it affects |
| [Running](user/running.md) | Start, stop, monitor with Docker Compose; local dev alternative |
| [Admin Guide](user/admin-guide.md) | Users, approvals, AI settings, prompts, FAQs |
| [AI Features](user/ai-features.md) | Provider setup, RAG documents, semantic search, profile generation |
| [Troubleshooting](user/troubleshooting.md) | Startup failures, port conflicts, DB errors, AI 503s |
| [FAQ](user/faq.md) | Quick answers to frequent operator questions |

---

## I want to contribute to Cosolvent

You are an engineer who wants to understand, extend, or maintain the codebase.

| Page | What it covers |
|------|---------------|
| [Developer Orientation](dev/index.md) | Codebase map, entry points, design principles |
| [Getting Started](dev/getting-started.md) | Local dev setup: clone → venv → run → test |
| [Architecture](dev/architecture.md) | System design, layers, data flow, design decisions |
| [Modules](dev/modules.md) | All modules: purpose, key files, router/service/repo pattern |
| [Compiler](dev/compiler.md) | `marketplace.yaml` → artifacts pipeline (all 4 stages) |
| [Engines](dev/engines.md) | Permission, schema, and visibility engines |
| [Data Models](dev/data-models.md) | All DB collections/tables, JSONB schemas, pgvector tables |
| [AI Architecture](dev/ai-architecture.md) | Multi-provider pattern, LLM client, RAG pipeline |
| [Workers](dev/workers.md) | ARQ workers, job types, background processing |
| [API Reference](dev/api-reference.md) | Complete endpoint reference with request/response shapes |
| [Testing](dev/testing.md) | Test strategy, fixtures, three tiers, running tests |
| [Contributing](dev/contributing.md) | Code style, PR process, module conventions, managed zones |

---

## Other Resources

- `README.md` — product overview and quick-start commands
- `WHITEPAPER.md` — the thin-market thesis and product philosophy
- `docs/thin-market-principles.md` — engineering stance on thin markets
- `docs/reference/SYSTEM_SPEC.md` — system specification reference
