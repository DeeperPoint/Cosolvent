# cosolvent-beta

Configurable marketplace backend compiler and runtime:
`FastAPI + Postgres (pgvector) + Redis (ARQ workers)`.

Goal: clone the repo, configure your marketplace in onboarding UI, generate deterministic artifacts, and ship a deployable package.

## Architecture in one line

`marketplace.yaml` is the source of truth.  
The compiler turns it into generated runtime code, migration artifacts, and an export package.

## Clone to running marketplace (recommended path)

### 1. Clone and prepare env

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
cp .env.example .env
```

Update `.env` as needed (minimum values that must be valid):

- `SESSION_SECRET`
- `MARKETPLACE_CONFIG_PATH` (default `marketplace.yaml`)
- If running outside Docker: `POSTGRES_DSN` + `REDIS_URL`
- Optional UI toggle: `ONBOARDING_V2_ENABLED=true|false` (default `true`).

### 2. Start onboarding service

```bash
make setup-up
make onboarding
```

Open `http://localhost:18080/onboarding`.

### 3. Configure and generate

In the onboarding panel:

1. Pick a preset template (or keep current config).
2. Configure marketplace identity, roles, onboarding rules, communication rules, and discovery rules.
3. Use in-context help tooltips and glossary for non-technical guidance.
4. Optionally open `Advanced JSON` mode for live validation + impact diff.
5. Click `Validate`.
6. Click `Save`.
7. Click `Generate Project` (mode `mvp` by default).

Generation writes managed outputs to:

- `app/generated/*`
- `generated/manifest.json`
- `openapi/generated_openapi.json`
- `alembic/versions/auto_marketplace_*.py`
- `exports/*.tar.gz` (if export enabled)

### 4. Start full stack

```bash
make up
make wait-api
```

Endpoints:

- API: `http://localhost:18000`
- Swagger: `http://localhost:18000/docs`
- Health: `http://localhost:18000/api/health`

### 5. Bootstrap admin

```bash
make bootstrap-admin
```

Default bootstrap credentials are controlled by Make vars:

- `ADMIN_EMAIL` (default `admin@example.com`)
- `ADMIN_PASSWORD` (default `ChangeMe123!`)

Example override:

```bash
make bootstrap-admin ADMIN_EMAIL=owner@yourmarket.com ADMIN_PASSWORD='StrongPass123!'
```

### 6. Stop services

```bash
make down        # stop containers
make reset       # stop + remove volumes
```

## Compiler workflow

### Generate from CLI

```bash
python -m cli compile --config marketplace.yaml --mode mvp
```

### Check drift (used by CI)

```bash
python -m cli compile --check --config marketplace.yaml --mode mvp
```

### Export deployable package

```bash
python -m cli export --config marketplace.yaml --mode mvp --export-dir exports
```

## Testing gate (same order used in CI/local validation)

```bash
make wait-api
make lint
make unit
make compile-check
make integration
make e2e
```

Notes:

- `make live` is optional for environments with live provider keys.

## Daily workflows

### Change marketplace behavior safely

1. Update config in onboarding UI (or edit `marketplace.yaml`).
2. Run `make compile`.
3. Run `make compile-check` to confirm deterministic sync.
4. Run tests (`make unit`, `make integration`, `make e2e`).

### Prepare a project handoff/export

1. `make export`
2. Take the generated `.tar.gz` in `exports/`.
3. Unpack in a new repo/environment.
4. Set environment values and run the same startup path (`make up`, `make wait-api`, `make bootstrap-admin`).

## Make targets

Run `make help` for full command list. Most-used targets:

- `make setup-up`, `make setup-down`
- `make up`, `make down`, `make reset`
- `make logs`, `make logs-api`, `make logs-worker`
- `make lint`, `make unit`, `make integration`, `make e2e`, `make live`, `make test-all`
- `make compile`, `make compile-check`, `make export`
- `make bootstrap-admin`, `make onboarding`

## Local (non-Docker) development

### 1. Prereqs

- Python `3.11+`
- Postgres `15+` with `pgvector` extension
- Redis

### 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure and run

```bash
cp .env.example .env
python -m cli validate marketplace.example.yaml
python -m cli wizard -o marketplace.yaml
python -m cli compile --config marketplace.yaml --mode mvp
```

Then run API and worker in separate terminals:

```bash
make api
```

```bash
make worker
```

## Common issues

### API fails on startup

- Verify Postgres is reachable and credentials are correct.
- Verify `pgvector` is available (`CREATE EXTENSION vector` supported).
- Verify `marketplace.yaml` exists at `MARKETPLACE_CONFIG_PATH`.

### Generated artifacts look stale

- Run `make compile`.
- Run `make compile-check` and inspect drift output.
- Ensure no manual edits were made inside managed generated zones.

### Worker is not processing jobs

- Check `make logs-worker`.
- Confirm `REDIS_URL` connectivity from API and worker containers.

### AI endpoints return `503`

Expected when AI provider credentials are missing/unavailable.  
Core non-AI marketplace flows should still function.

## Documentation

- `docs/getting-started.md`
- `docs/testing.md`
- `docs/generation.md`
- `docs/architecture.md`
- `docs/data-models.md`
