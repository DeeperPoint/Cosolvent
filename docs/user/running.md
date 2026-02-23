# Running Cosolvent

How to start, stop, and monitor the Cosolvent stack — with Docker Compose (recommended) or locally.

## Docker Compose (Recommended)

Docker Compose starts all services (API, worker, Postgres, Redis) with a single command.

### Start the Stack

```bash
make up
# or
API_HOST_PORT=18000 docker compose up -d --build
```

Wait for the API to become healthy (polls until ready, up to 3 minutes):

```bash
make wait-api
# or
python scripts/wait_for_http.py --url http://localhost:18000/api/health --timeout 180
```

### Stop the Stack

```bash
make down
# or
docker compose down
```

To also remove volumes (clears the database and Redis data):

```bash
docker compose down -v
```

### Services

| Service | Default Port | Purpose |
|---------|-------------|---------|
| `api` | `18000` | FastAPI application |
| `worker` | — | ARQ background worker (no HTTP port) |
| `postgres` | `5432` | Postgres + pgvector |
| `redis` | `6379` | Redis (sessions + job queue) |
| `setup` | `18080` | Setup wizard (separate service, used only for config) |

### Health Check

```bash
curl http://localhost:18000/api/health
```

Returns:

```json
{"status": "ok", "marketplace": "Your Marketplace Name"}
```

Swagger UI: `http://localhost:18000/docs`

---

## Setup Service (Wizard Only)

The setup service is a separate, lightweight container used only during initial configuration and re-configuration. Do not run it alongside the main API in production.

```bash
# Start wizard
make setup-up

# Stop wizard
make setup-down
```

Wizard URL: `http://localhost:18080/onboarding`

---

## Port Configuration

Change the API port without modifying `docker-compose.yml`:

```bash
API_HOST_PORT=19000 docker compose up -d --build
```

Then access `http://localhost:19000` instead.

---

## Viewing Logs

All services:

```bash
docker compose logs -f
```

Specific service:

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres
```

---

## Re-Running After Config Changes

When you update `marketplace.yaml` (or re-run the wizard and regenerate):

1. **Recompile** (if you edited `marketplace.yaml` manually):
   ```bash
   make compile
   ```

2. **Restart the stack**:
   ```bash
   make down
   make up
   make wait-api
   ```

The database migration (`alembic/versions/auto_marketplace_*.py`) runs automatically on startup. There is no separate migration step.

---

## Makefile Reference

| Target | Command | Description |
|--------|---------|-------------|
| `make up` | `docker compose up -d --build` | Start full stack |
| `make down` | `docker compose down` | Stop stack (keep volumes) |
| `make wait-api` | `python scripts/wait_for_http.py ...` | Poll until API is healthy |
| `make setup-up` | Start setup container only | For wizard access |
| `make setup-down` | Stop setup container | After wizard use |
| `make bootstrap-admin` | POST to `/api/auth/bootstrap` | Create first admin |
| `make compile` | Run compiler pipeline | After config changes |
| `make compile-check` | Verify artifact sync | CI gate |
| `make logs` | `docker compose logs -f` | Follow all logs |

---

## Local Development (Without Docker)

For development without Docker, you need:
- Python 3.11+
- Postgres 15+ with `pgvector` extension
- Redis

```bash
# Create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your local DB/Redis credentials

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run the worker (separate terminal)
arq app.workers.settings.WorkerSettings
```

API available at `http://localhost:8000`.

---

## See Also
- [Quick Start](quick-start.md) — end-to-end setup
- [Environment Variables](environment.md) — configuring `.env`
- [Troubleshooting](troubleshooting.md) — startup failures, port conflicts, and more
