# Architecture

## Overview

Cosolvent is a configurable single-marketplace backend built on:

- FastAPI
- Postgres + pgvector
- Redis + ARQ workers
- S3-compatible storage

`marketplace.yaml` remains the source of truth for marketplace behavior.  
The onboarding/setup service can now compile that config into deterministic generated artifacts (role aliases, policy matrices, migration metadata seed, OpenAPI snapshot, export archive).

## Runtime Shape

### Core runtime

- `app/main.py`: API app factory and router registration.
- `app/core/`: shared infra (settings, DB proxy/session, redis, middleware, dependencies).
- `app/modules/*`: feature modules (`router -> service -> repository -> storage`).
- `app/engine/*`: config-driven runtime engines for schema validation, permissions, and visibility.
- `app/workers/*`: async processing for indexing/email/document flows.

### Setup runtime

- `app/setup_app.py`: standalone setup app that does not require DB/API startup.
- `app/modules/setup/router.py`: onboarding UI + setup APIs (`validate`, `render-yaml`, `save`, `generate`, `generate/check`).

## Compiler and Managed Zones

Compiler package: `app/compiler/`

- `normalize.py`: validates + canonicalizes config and computes stable `spec_hash`.
- `ir.py`: compile IR + options.
- `render.py`: deterministic file rendering.
- `writer.py`: managed-zone writes and stale artifact pruning.
- `manifest.py`: generation manifest and sync metadata.
- `exporter.py`: `.tar.gz` export packaging.
- `service.py`: orchestration for compile/check and OpenAPI snapshot.

Managed output zones:

- `app/generated/*`
- `alembic/versions/auto_marketplace_*.py`
- `openapi/generated_openapi.json`
- `generated/manifest.json`
- `exports/*.tar.gz` (optional)

Regeneration only mutates managed zones and never touches handwritten files outside those zones.

## Endpoint Compatibility Strategy

Generic endpoints stay intact (example: `/api/profiles/{type_slug}/...`).

Generated role aliases are additive, e.g.:

- `/api/roles/producer/register`
- `/api/roles/producer/draft`
- `/api/roles/producer/me`
- `/api/roles/producer/{profile_id}`

`app/main.py` loads generated aliases when `app/generated/role_alias_router.py` exists.

## Data Strategy

Operational data remains on shared document-style JSONB tables (`users`, `profiles`, `applications`, etc.) plus vector tables.

Generated migration adds marketplace metadata tables:

- `marketplace_roles`
- `marketplace_role_permissions`
- `marketplace_onboarding_rules`
- `marketplace_communication_rules`
- `marketplace_profile_field_defs`
- `marketplace_builds`

This hybrid approach preserves existing runtime behavior while giving deterministic, queryable marketplace metadata.

## Generation/CI Contract

- Source input: `marketplace.yaml`
- Determinism: canonical JSON + stable `spec_hash`
- CI gate: `python -m cli compile --check --config marketplace.yaml --mode mvp`
- Build fails if generated artifacts drift from config

## High-Level Flow

1. Clone repo.
2. Run setup service and complete onboarding.
3. Save config.
4. Generate project artifacts.
5. Start full stack and deploy or export package.
