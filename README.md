# cosolvent-beta

Configurable marketplace backend compiler/runtime built with:
`FastAPI + Postgres (pgvector) + Redis (ARQ workers)`.

The product flow is:
`clone repo -> onboarding UI -> generate -> deploy`.

## Requirements

- Docker + Docker Compose
- Python `3.11+` (for local CLI/testing)
- Postgres with `pgvector` support (if running outside Docker)

## Quick Start

### 1. Clone and configure env

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
cp .env.example .env
```

Minimum env values to set:

- `SESSION_SECRET`
- `MARKETPLACE_CONFIG_PATH` (default `marketplace.yaml`)
- For non-Docker local runtime: `POSTGRES_DSN` and `REDIS_URL`

### 2. Launch onboarding (V2 is default and only UI)

```bash
make setup-up
make onboarding
```

Open:
`http://localhost:18080/onboarding`

### 3. Configure and generate

In onboarding:

1. Select a preset (or keep existing config).
2. Complete guided steps (roles, onboarding rules, communication, discovery).
3. Validate and save config.
4. Click `Generate Project`.

### 4. Start full stack

```bash
make up
make wait-api
```

Useful URLs:

- API: `http://localhost:18000`
- Swagger docs: `http://localhost:18000/docs`
- Health: `http://localhost:18000/api/health`

### 5. Bootstrap admin

```bash
make bootstrap-admin
```

Optional override:

```bash
make bootstrap-admin ADMIN_EMAIL=owner@yourmarket.com ADMIN_PASSWORD='StrongPass123!'
```

### 6. Stop/reset

```bash
make down
make reset
```

## Compiler Workflow

Generate:

```bash
python -m cli compile --config marketplace.yaml --mode mvp
```

Check drift:

```bash
python -m cli compile --check --config marketplace.yaml --mode mvp
```

Export package:

```bash
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

## Generated Artifact Policy

`marketplace.yaml` is the source of truth. Generated files are managed outputs:

- `app/generated/*`
- `generated/manifest.json`
- `openapi/generated_openapi.json`
- `alembic/versions/auto_marketplace_*.py`

Team workflow:

1. Run generation locally (`make compile`) when changing config/compiler behavior.
2. Do not hand-edit generated files.
3. Keep commits focused on source/docs/tests unless artifact updates are explicitly required.

## Testing

Recommended gate:

```bash
make wait-api
make lint
make unit
make compile-check
make integration
make e2e
```

`make live` is optional and only for environments with real provider credentials.

## Common Commands

Run `make help` for full list. Most used:

- `make setup-up`, `make setup-down`
- `make up`, `make down`, `make reset`
- `make compile`, `make compile-check`, `make export`
- `make lint`, `make unit`, `make integration`, `make e2e`
- `make logs`, `make logs-api`, `make logs-worker`

## Local (Non-Docker) Dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m cli validate marketplace.example.yaml
python -m cli wizard -o marketplace.yaml
python -m cli compile --config marketplace.yaml --mode mvp
make api
# in another shell:
make worker
```

## Troubleshooting

### API startup failure

- Verify Postgres credentials/connectivity.
- Verify pgvector support (`CREATE EXTENSION vector`).
- Verify `MARKETPLACE_CONFIG_PATH` points to an existing YAML file.

### Compile check fails

- Run `make compile`.
- Re-run `make compile-check` and inspect drift list.

### Worker jobs not processing

- Check `make logs-worker`.
- Confirm Redis connectivity via `REDIS_URL`.

### AI endpoints return `503`

Expected when provider credentials are missing/unavailable. Core non-AI flows should still work.

## Docs

- `docs/getting-started.md`
- `docs/testing.md`
- `docs/generation.md`
- `docs/architecture.md`
- `docs/data-models.md`
