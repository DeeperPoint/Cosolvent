# Getting Started (Dev)

Set up a local development environment from scratch: Python env, database, running the API and worker, and running the test suite.

## Prerequisites

- Python 3.11+
- Postgres 15+ with `pgvector` extension installed
- Redis 6+
- Git

> **Tip:** If you just want to run the platform (not develop it), use Docker Compose instead — see [Quick Start](../user/quick-start.md).

---

## 1. Clone and Install

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
```

### With `uv` (recommended)

```bash
uv sync
```

### With pip

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `dev` extras include `pytest`, `ruff`, `httpx`, and other development tools.

---

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your local credentials. Minimum required:

```env
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/cosolvent
REDIS_URL=redis://localhost:6379
SESSION_SECRET=dev-secret-change-me
MARKETPLACE_CONFIG_PATH=marketplace.yaml
```

> **Note:** `SESSION_SECRET` must be a non-empty string. Anything works for local dev; change it before deploying anywhere.

---

## 3. Set Up Postgres

Create the database:

```bash
psql -U postgres -c "CREATE DATABASE cosolvent;"
```

Enable pgvector:

```bash
psql -U postgres -d cosolvent -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Run Alembic migrations:

```bash
.venv/bin/alembic upgrade head
```

---

## 4. Create a Marketplace Config

If you don't have a `marketplace.yaml` yet:

```bash
# Interactive wizard (CLI)
.venv/bin/python -m cli wizard -o marketplace.yaml

# Or use the example config
cp marketplace.example.yaml marketplace.yaml
```

Compile the generated artifacts:

```bash
.venv/bin/python -m cli compile --config marketplace.yaml --mode mvp
```

---

## 5. Run the API

```bash
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

The `--reload` flag restarts the server automatically on Python file changes.

---

## 6. Run the Worker

In a separate terminal:

```bash
.venv/bin/arq app.workers.settings.WorkerSettings
```

The worker processes background jobs (document indexing, profile indexing, email sending). The API queues jobs to Redis; the worker picks them up.

---

## 7. Run the Setup Service (Optional)

To use the browser wizard for local dev:

```bash
.venv/bin/uvicorn app.setup_app:setup_app --host 0.0.0.0 --port 18080
```

Open `http://localhost:18080/onboarding`.

---

## 8. Bootstrap Admin

```bash
curl -X POST http://localhost:8000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "ChangeMe123!"}'
```

---

## Running Tests

### Lint

```bash
.venv/bin/ruff check app cli tests scripts
```

### Unit tests (no infrastructure required)

```bash
.venv/bin/pytest tests/unit -q
```

### Integration tests (requires running stack)

```bash
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:8000 \
  .venv/bin/pytest tests/integration -q
```

### E2E tests (requires running stack)

```bash
RUN_E2E=1 E2E_BASE_URL=http://localhost:8000 \
  .venv/bin/pytest tests/e2e/test_local_full_stack.py -q
```

### Compile-check (CI gate)

```bash
.venv/bin/python -m cli compile --check --config marketplace.yaml --mode mvp
```

---

## Editor Setup

### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance
- Ruff (charliermarsh.ruff)

Workspace settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm

Set the interpreter to `.venv/bin/python`. Enable Ruff as an external tool for formatting.

---

## Daily Workflow

```bash
# 1. Lint
.venv/bin/ruff check app cli tests scripts

# 2. Run unit tests
.venv/bin/pytest tests/unit -q

# 3. Check artifacts sync (after any config changes)
.venv/bin/python -m cli compile --check --config marketplace.yaml --mode mvp
```

---

## See Also
- [Architecture](architecture.md) — how the system is structured
- [Testing](testing.md) — test strategy and fixture details
- [Contributing](contributing.md) — code style, PR process

---

[← Developer Orientation](index.md) · [Architecture →](architecture.md)
