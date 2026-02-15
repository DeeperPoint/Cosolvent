# cosolvent-beta

Configurable marketplace backend platform (FastAPI + Postgres/pgvector + Redis + ARQ workers), with dynamic onboarding and marketplace behavior driven by YAML config.

Repository: `https://github.com/DeeperPoint/cosolvent-beta`

## What you get

- Config-driven participant types, permissions, profile schemas, onboarding, communication, and discovery rules
- Auth + sessions + admin workflows
- Profile lifecycle (draft, submit, approve/reject)
- Conversations, messages, notifications, websocket support
- Search/discovery with optional AI/vector flows (pgvector)
- Background workers for indexing and async tasks

## Quick Start (Docker)

### 1. Clone

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
```

### 2. Start full stack

```bash
API_HOST_PORT=18000 docker compose up -d --build
python scripts/wait_for_http.py --url http://localhost:18000/api/health --timeout 180
```

You get:

- API: `http://localhost:18000`
- Swagger: `http://localhost:18000/docs`

### 3. Bootstrap first admin

```bash
curl -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

### 4. Stop stack

```bash
docker compose down -v
```

## Local Development (No Docker)

### 1. Prerequisites

- Python `3.11+`
- Postgres `15+` with `pgvector` extension enabled
- Redis

### 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure env

```bash
cp .env.example .env
```

Minimum required values:

- `POSTGRES_DSN` (or discrete `POSTGRES_*` vars)
- `REDIS_URL`
- `SESSION_SECRET`
- `MARKETPLACE_CONFIG_PATH`

### 4. Generate or choose marketplace config

```bash
python -m cli wizard -o marketplace.yaml
# or
python -m cli wizard --preset agriculture -o marketplace.yaml
# or
cp marketplace.example.yaml marketplace.yaml
```

Validate config:

```bash
python -m cli validate marketplace.yaml
```

### 5. Run API + worker

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
arq app.workers.settings.WorkerSettings
```

## Tests

```bash
ruff check app cli tests scripts
pytest tests/unit -q
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -q
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -q
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -q -rs
```

Live-provider E2E runs only when required secrets are present; otherwise it skips with an explicit reason.

## Troubleshooting

### API won't start because of DB

- Confirm Postgres is reachable.
- Confirm `POSTGRES_DSN` is correct.
- Confirm the DB allows `CREATE EXTENSION vector`.

### Worker not processing tasks

- `docker compose logs -f worker`
- Confirm Redis connectivity from API + worker.

### AI endpoints return `503`

Expected when `OPENAI_API_KEY` is missing; core non-AI flows still work.
