# Generation and Export

## Goal

Convert `marketplace.yaml` into deterministic, deployable project artifacts. The compiler reads your marketplace configuration and produces all the code, migrations, and API specifications needed to run the marketplace.

## Commands

```bash
# Generate managed artifacts
python -m cli compile --config marketplace.yaml --mode mvp

# Check if generated files are in sync
python -m cli compile --check --config marketplace.yaml --mode mvp

# Generate and export package
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

Or via Make targets:

```bash
make compile         # Generate artifacts
make compile-check   # Verify artifacts are in sync
make export          # Generate + create tarball
```

## Setup API

The setup module exposes generation endpoints for the onboarding UI:

- `POST /api/setup/generate` — Trigger artifact generation
- `POST /api/setup/generate/check` — Check artifact freshness

Both accept optional inline config payload; when omitted, runtime config is used.

## How the Compiler Works

The compilation pipeline has four stages:

### 1. Normalize

`compiler/normalize.py` — Reads `marketplace.yaml` and normalizes it into a canonical internal representation. Defaults are filled in, field orders are stabilized, and the config is validated against the `MarketplaceConfig` Pydantic model.

### 2. Intermediate Representation

`compiler/ir.py` — Transforms the normalized config into an intermediate representation (IR) that describes every artifact to be generated. The IR is a pure data structure with no side effects.

### 3. Render

`compiler/render.py` — Takes the IR and produces file contents. Each output file is rendered deterministically: same input always produces the same output. This is the largest module and handles Python code generation, SQL migration generation, and OpenAPI spec generation.

### 4. Write

`compiler/writer.py` — Writes rendered files to disk inside managed zones. Only managed zone paths are touched; user code is never overwritten.

## Determinism Contract

1. Config is normalized and validated via `MarketplaceConfig`.
2. Compiler serializes canonical JSON and computes `spec_hash` (SHA-256).
3. Renderer writes deterministic outputs to managed zones.
4. Manifest records spec hash, mode, file list, migration revision, and optional export path.

**Same config in → same artifacts out.** This is enforced by the compile-check gate.

## Managed Zones

Only these directories/files are written by the compiler:

- `app/generated/*` — Python modules (enums, models, registries, routers)
- `alembic/versions/auto_marketplace_*.py` — Database migration
- `openapi/generated_openapi.json` — OpenAPI specification
- `generated/manifest.json` — Build manifest with hashes and metadata
- `exports/*.tar.gz` — Deployable archive (if export is enabled)

**Do not hand-edit files in managed zones.** They will be overwritten on the next compile.

## Generated Artifacts

| File | Purpose |
|------|---------|
| `app/generated/marketplace_spec.py` | Parsed marketplace configuration as Python dataclass |
| `app/generated/role_registry.py` | Role definitions and slug mappings |
| `app/generated/role_alias_router.py` | Role-based route aliases (e.g. `/api/producers/...`) |
| `app/generated/profile_models.py` | Dynamic Pydantic models for profile field validation |
| `app/generated/policy_matrix.py` | Permission and visibility matrices |
| `app/generated/enums.py` | Generated enums from config values |
| `alembic/versions/auto_marketplace_*.py` | Database migration for marketplace metadata tables |
| `openapi/generated_openapi.json` | Full OpenAPI 3.1 specification |
| `generated/manifest.json` | Build metadata, hashes, and file inventory |

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

## CI Gate

```bash
python -m cli compile --check --config marketplace.yaml --mode mvp
```

CI fails when:

- generated files are missing,
- contents drift from current config,
- stale managed files remain,
- manifest `spec_hash` does not match expected hash.

## Export Format

The `export` command generates artifacts and bundles them into a timestamped tarball:

```
exports/marketplace-<short-hash>.tar.gz
```

The tarball contains all generated files plus the manifest, suitable for deployment or handoff.
