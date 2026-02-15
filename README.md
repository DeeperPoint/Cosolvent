# cosolvent-beta

Configurable marketplace backend platform (FastAPI + MongoDB + Redis + workers), with dynamic onboarding and marketplace behavior driven by YAML config.

Repository: `https://github.com/DeeperPoint/cosolvent-beta`

## What you get

- Config-driven participant types, permissions, profile schemas, onboarding, communication, and discovery rules
- Auth + sessions + admin workflows
- Profile lifecycle (draft, submit, approve/reject)
- Conversations, messages, notifications, websocket support
- Search/discovery with optional AI/vector flows
- Background workers for indexing and async tasks

## Quick Start (Recommended: Docker)

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

The API is now available at:

- API: `http://localhost:18000`
- Swagger docs: `http://localhost:18000/docs`

### 3. Bootstrap first admin

Run once on a fresh database:

```bash
curl -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

### 4. Validate config (optional)

```bash
python -m cli validate marketplace.example.yaml
```

### 5. Stop stack

```bash
docker compose down -v
```

## Local Development (Without Docker)

Use this if you want fast iteration on code.

### 1. Prerequisites

- Python `3.11+`
- MongoDB running (`mongodb://localhost:27017`)
- Redis running (`redis://localhost:6379`)

### 2. Create virtual environment + install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Environment file

Create `.env` from example:

```bash
cp .env.example .env
```

Minimum required values to run core flows:

- `MONGODB_URI`
- `MONGODB_DATABASE`
- `REDIS_URL`
- `SESSION_SECRET`
- `MARKETPLACE_CONFIG_PATH`

Optional provider keys (AI/email/S3):

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `COHERE_API_KEY`
- `RESEND_API_KEY`
- `EMAIL_FROM`
- `S3_BUCKET`
- `S3_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### 4. Create your marketplace config

#### Option A: Wizard (interactive)

```bash
python -m cli wizard -o marketplace.yaml
```

#### Option B: Preset

```bash
python -m cli wizard --preset agriculture -o marketplace.yaml
# or
python -m cli wizard --preset professional_services -o marketplace.yaml
```

#### Option C: Start from example

```bash
cp marketplace.example.yaml marketplace.yaml
```

Validate:

```bash
python -m cli validate marketplace.yaml
```

### 5. Run API + worker

API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Worker (second terminal):

```bash
arq app.workers.settings.WorkerSettings
```

Local API URL:

- `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Running Tests

### Lint + unit

```bash
ruff check app cli tests scripts
pytest tests/unit -q
```

### Integration (requires running stack)

```bash
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -q
```

### Local full-stack E2E (requires running stack)

```bash
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -q
```

### Live-provider E2E (only if keys exist)

```bash
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -q -rs
```

If required secrets are missing, live-provider tests skip with an explicit reason.

## Common First API Calls

Health:

```bash
curl http://localhost:18000/api/health
```

Login:

```bash
curl -X POST http://localhost:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

## Setup Wizard Tips

- Keep marketplace MVP simple first: 2 participant types, 1 conversation rule
- Mark only truly searchable fields as `searchable: true`
- Use `requires_approval: true` for supply-side roles if trust is critical
- Re-run wizard anytime and re-validate config before boot

## Troubleshooting

### Port already in use

Change exposed API port:

```bash
API_HOST_PORT=19000 docker compose up -d --build
```

Then use `http://localhost:19000`.

### "Marketplace config not loaded" or bad config errors

- Validate config:
  - `python -m cli validate marketplace.yaml`
- Ensure `MARKETPLACE_CONFIG_PATH` points to the file you expect

### Worker not processing tasks

- Confirm worker is running:
  - `docker compose logs -f worker`
  - or local `arq app.workers.settings.WorkerSettings`
- Confirm Redis is reachable from API/worker

### AI endpoints return 503

This is expected when AI providers are not configured. Core non-AI flows remain available.

## CI Gate (what must pass)

- `ruff check app cli tests`
- `pytest tests/unit`
- `pytest tests/integration`
- local full-stack E2E
- live-provider E2E when provider secrets are configured

---

If you cloned this repo and followed either Quick Start or Local Development, you should now be ready to use and extend the platform.
