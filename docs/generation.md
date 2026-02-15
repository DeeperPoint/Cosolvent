# Generation and Export

## Goal

Convert `marketplace.yaml` into deterministic, deployable project artifacts.

## Commands

```bash
# Generate managed artifacts
python -m cli compile --config marketplace.yaml --mode mvp

# Check if generated files are in sync
python -m cli compile --check --config marketplace.yaml --mode mvp

# Generate and export package
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

## Setup API

- `POST /api/setup/generate`
- `POST /api/setup/generate/check`

Both accept optional inline config payload; when omitted, runtime config is used.

## Determinism Contract

1. Config is normalized and validated via `MarketplaceConfig`.
2. Compiler serializes canonical JSON and computes `spec_hash` (SHA-256).
3. Renderer writes deterministic outputs to managed zones.
4. Manifest records spec hash, mode, file list, migration revision, and optional export path.

## Managed Zones

- `app/generated/*`
- `alembic/versions/auto_marketplace_*.py`
- `openapi/generated_openapi.json`
- `generated/manifest.json`
- `exports/*.tar.gz` (if enabled)

Only managed zones are rewritten/pruned during regeneration.

## Generated Artifacts

- `app/generated/marketplace_spec.py`
- `app/generated/role_registry.py`
- `app/generated/role_alias_router.py`
- `app/generated/profile_models.py`
- `app/generated/policy_matrix.py`
- `alembic/versions/auto_marketplace_<revision>.py`
- `openapi/generated_openapi.json`
- `generated/manifest.json`

## CI Gate

`python -m cli compile --check --config marketplace.yaml --mode mvp`

CI fails when:

- generated files are missing,
- contents drift from current config,
- stale managed files remain,
- manifest `spec_hash` does not match expected hash.
