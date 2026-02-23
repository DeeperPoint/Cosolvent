# Compiler

The compiler converts `marketplace.yaml` into deterministic, deployable project artifacts. It runs offline (via CLI or the setup API) and outputs Python modules, database migrations, and an OpenAPI spec.

## Overview

```
marketplace.yaml
      │
      ▼
┌─────────────────────┐
│ 1. Normalize         │  compiler/normalize.py
│    Parse + validate  │  → MarketplaceConfig (Pydantic)
│    Fill defaults     │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2. IR Generation     │  compiler/ir.py
│    Config → pure     │  → IntermediateRepresentation
│    data structures   │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 3. Render            │  compiler/render.py
│    IR → file text    │  → Dict[filepath, content]
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4. Write             │  compiler/writer.py
│    Emit to disk      │  → Files on disk + manifest.json
│    Managed zones     │
└─────────────────────┘
```

## Stage 1 — Normalize (`compiler/normalize.py`)

Reads the raw YAML and validates it through the `MarketplaceConfig` Pydantic model. Fills in defaults, stabilizes field ordering, and returns a canonical internal representation. Any validation error raised here prevents compilation.

This stage also computes the `spec_hash`: a SHA-256 of the JSON-serialized canonical config. The spec_hash is the fingerprint of a compilation — same config always produces the same hash.

## Stage 2 — Intermediate Representation (`compiler/ir.py`)

Transforms the normalized `MarketplaceConfig` into an IR — a pure data structure with no side effects. The IR describes every artifact to be generated: which Python modules to emit, which database tables to create, which API routes to register, which Pydantic models to generate.

Separating config from IR makes the render stage independently testable.

## Stage 3 — Render (`compiler/render.py`)

Takes the IR and produces file contents. Every output file is rendered deterministically — same IR always produces the same text. This stage handles:
- Python code generation (enums, models, registries, routers)
- SQL migration generation (marketplace metadata tables)
- OpenAPI spec generation

The render stage is the largest module. If you need to change what generated code looks like, start here.

## Stage 4 — Write (`compiler/writer.py`)

Writes rendered files to disk. The writer enforces managed zones: it checks every output path against the allowed zone list before writing. Any path outside a managed zone raises an error — user code is never overwritten.

The writer also:
- Prunes stale managed files (present in the previous manifest but not in the current render)
- Creates the manifest (`generated/manifest.json`) with spec_hash, file list, migration revision, and timestamp
- Optionally creates a tarball export

## Commands

```bash
# Generate managed artifacts
python -m cli compile --config marketplace.yaml --mode mvp

# Verify artifacts are in sync (CI gate — does not write files)
python -m cli compile --check --config marketplace.yaml --mode mvp

# Generate and create an export archive
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

Or via Make:

```bash
make compile          # Generate artifacts
make compile-check    # CI sync gate
make export           # Generate + tarball
```

## Setup API

The setup service exposes compilation via HTTP (used by the wizard):

```
POST /api/setup/generate
POST /api/setup/generate/check
```

Both accept an optional inline config payload; when omitted, the runtime config is used.

## Generated Artifacts

| File | Purpose |
|------|---------|
| `app/generated/marketplace_spec.py` | Parsed marketplace config as a Python dataclass — imported by modules that need config values at import time |
| `app/generated/role_registry.py` | Role definitions and slug-to-name mappings |
| `app/generated/role_alias_router.py` | FastAPI router with role-based route aliases (e.g. `/api/roles/producer/...`) |
| `app/generated/profile_models.py` | Dynamic Pydantic models for profile field validation, one per participant type |
| `app/generated/policy_matrix.py` | Permission and visibility decision matrices derived from config |
| `app/generated/enums.py` | Python enums from config values (participant type slugs, field types) |
| `alembic/versions/auto_marketplace_*.py` | Database migration for marketplace metadata tables |
| `openapi/generated_openapi.json` | Full OpenAPI 3.1 specification |
| `generated/manifest.json` | Build metadata (spec_hash, mode, files, migration revision, timestamp) |

## Manifest Format

```json
{
  "spec_hash": "sha256:abc123...",
  "mode": "mvp",
  "generated_at": "2026-02-20T10:30:00Z",
  "generated_files": ["app/generated/enums.py", "..."],
  "migration_revision": "cd0965b20114",
  "export_path": "exports/marketplace-abc123.tar.gz"
}
```

## Determinism Contract

1. Config is validated and normalized via `MarketplaceConfig`
2. Canonical JSON is serialized and hashed → `spec_hash`
3. Same config → same `spec_hash` → same artifacts
4. The `compile --check` command verifies this invariant by comparing current file contents against a fresh render

## Managed Zones

Only these paths are written by the compiler:

```
app/generated/*
alembic/versions/auto_marketplace_*.py
openapi/generated_openapi.json
generated/manifest.json
exports/*.tar.gz
```

> **Warning:** Do not hand-edit files in managed zones. They will be overwritten on the next compile.

## CI Gate

```bash
python -m cli compile --check --config marketplace.yaml --mode mvp
```

CI fails when:
- Generated files are missing
- File contents have drifted from the current config
- Stale managed files remain from a previous config
- `manifest.spec_hash` does not match the expected hash

## Export Format

```bash
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

Creates a timestamped tarball:

```
exports/marketplace-<short-hash>.tar.gz
```

Contains all generated files plus the manifest. Used for deployment handoff or archiving a specific build.

## See Also
- [Architecture](architecture.md) — how the compiler fits in the system
- [Modules](modules.md) — setup module (wizard + compile API)
- [Contributing](contributing.md) — managed zones, what not to edit

---

[← Modules](modules.md) · [Engines →](engines.md)
