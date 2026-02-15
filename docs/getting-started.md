
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

The API is available at:

- API: `http://localhost:18000`
- Swagger docs: `http://localhost:18000/docs`

### 3. Bootstrap first admin

```bash
curl -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

### 4. Optional config validation

```bash
python -m cli validate marketplace.example.yaml
```

### 5. Stop stack

```bash
docker compose down -v
```

## Local Development (Without Docker)

### 1. Prerequisites

- Python `3.11+`
- MongoDB running on `mongodb://localhost:27017` (or update `.env`)
- Redis running on `redis://localhost:6379` (or update `.env`)

### 2. Create virtual environment + install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
cp .env.example .env
```

Minimum required values for core flows:

- `MONGODB_URI`
- `MONGODB_DATABASE`
- `REDIS_URL`
- `SESSION_SECRET`
- `MARKETPLACE_CONFIG_PATH`

### 4. Create marketplace config

Wizard:

```bash
python -m cli wizard -o marketplace.yaml
```

Preset:

```bash
python -m cli wizard --preset agriculture -o marketplace.yaml
# or
python -m cli wizard --preset professional_services -o marketplace.yaml
```

From example:

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

Worker:

```bash
arq app.workers.settings.WorkerSettings
```

Local URLs:

- API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

## Running Tests

```bash
# Lint
ruff check app cli tests scripts

# Unit
pytest tests/unit -q

# Integration (requires running stack)
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -q

# Local full-stack E2E (requires running stack)
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -q

# Live-provider E2E (only when provider keys are present)
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -q -rs
```

## Troubleshooting

### Port already in use

```bash
API_HOST_PORT=19000 docker compose up -d --build
```

Then use `http://localhost:19000`.

### Config load issues

- Validate config:
  - `python -m cli validate marketplace.yaml`
- Ensure `MARKETPLACE_CONFIG_PATH` in `.env` points to the right file.

### Worker not processing

- `docker compose logs -f worker`
- Verify Redis connectivity and that worker process is running.

### AI endpoints return `503`

Expected when provider keys are missing. Non-AI core flows still run.

