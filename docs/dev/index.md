# Developer Orientation

Welcome to the Cosolvent codebase. This page gives you a map of how the project is organized, where things live, and how to orient yourself for common tasks.

## Codebase Map

```
cosolvent-beta/
├── app/
│   ├── main.py              # App factory, router registration, lifespan
│   ├── setup_app.py         # Separate setup-only app (wizard + generation)
│   ├── core/                # Settings, DB, middleware, dependencies
│   ├── modules/             # Domain modules (auth, profiles, files, ...)
│   ├── engine/              # Permission, schema, visibility engines
│   ├── compiler/            # marketplace.yaml → artifact pipeline
│   ├── generated/           # Compiler output (managed zone — do not edit)
│   └── workers/             # ARQ background tasks
├── cli/                     # CLI entry point (wizard, validate, compile)
├── tests/                   # unit/, integration/, e2e/, test_config/
├── alembic/                 # Database migrations
├── openapi/                 # Generated OpenAPI spec (managed zone)
├── generated/               # manifest.json (managed zone)
├── marketplace.yaml         # Config source of truth
└── docker-compose.yml       # Service definitions
```

## Entry Points

| Entry point | What it starts |
|-------------|---------------|
| `app/main.py` | Main FastAPI app (API + WebSockets). Loads generated routers when present. |
| `app/setup_app.py` | Setup-only FastAPI app. Serves the wizard and compilation endpoints. Never runs alongside `main.py`. |
| `cli/__main__.py` | CLI: `python -m cli wizard \| validate \| compile \| export` |
| `app/workers/settings.py` | ARQ worker settings. Run with `arq app.workers.settings.WorkerSettings`. |

## Key Design Principles

### 1. Config-driven behavior
Every marketplace-specific behavior (roles, permissions, profile schemas, approval rules, discovery) is defined in `marketplace.yaml`. The runtime reads this at startup and uses it everywhere — no hardcoded role names, no hardcoded field names.

### 2. Deterministic generation
The compiler converts `marketplace.yaml` into code, migrations, and API specs. Same config in → same output out. The `spec_hash` (SHA-256 of normalized config) is embedded in the manifest for CI verification.

### 3. Managed zones
Generated files live in managed directories and are never hand-edited. The compiler prunes stale files and regenerates fresh on each compile. Safe to commit generated files alongside config.

### 4. Separation of setup and runtime
The wizard and compiler run in a separate FastAPI app (`setup_app.py`). This keeps setup dependencies isolated from the production runtime. The two apps never run simultaneously.

### 5. Document model over Postgres
Operational entities (users, profiles, conversations, etc.) use a JSONB document model over Postgres tables. This gives MongoDB-like flexibility while retaining pgvector, transactions, and reliable indexes.

## How Config Flows Into Runtime

```
marketplace.yaml
     │
     ▼ (startup)
MarketplaceConfig (Pydantic)   ←── app/core/marketplace_config.py
     │
     ├── Permission engine     ←── app/engine/permission_engine.py
     ├── Schema engine         ←── app/engine/schema_engine.py
     └── Visibility engine     ←── app/engine/visibility_engine.py

(compile time)
marketplace.yaml → compiler → app/generated/
                            → alembic/versions/auto_marketplace_*.py
                            → openapi/generated_openapi.json
```

## Where to Start for Common Tasks

| Task | Start here |
|------|-----------|
| Add an API endpoint | `app/modules/<module>/router.py` |
| Change business logic | `app/modules/<module>/service.py` |
| Change DB queries | `app/modules/<module>/repository.py` |
| Change permission checks | `app/engine/permission_engine.py` |
| Change profile field validation | `app/engine/schema_engine.py` |
| Change what's visible to whom | `app/engine/visibility_engine.py` |
| Change compiler output | `app/compiler/render.py` |
| Add a background job | `app/workers/` |
| Add a CLI command | `cli/__main__.py` |
| Add a wizard preset | `app/modules/setup/presets.py` |

## See Also
- [Getting Started](getting-started.md) — dev environment setup
- [Architecture](architecture.md) — system design and layers
- [Modules](modules.md) — every module in detail
- [Contributing](contributing.md) — code style, PR process, managed zones

---

[Next: Getting Started →](getting-started.md)
