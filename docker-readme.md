<!--Copyright (c) 2026 Mustafa Uzumeri. All rights reserved.-->

# Cosolvent — Docker Launch Guide

Cosolvent ships with a complete, production-patterned Docker Compose stack. No additional containerization work is needed — follow the steps below to get the full stack running locally.

---

## Stack Overview

The `docker-compose.yml` defines six services:

| Service | Image / Source | Purpose | Host Port |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | PostgreSQL with vector extension | `15432` |
| `redis` | `redis:7` | Job queue backend for `arq` worker | *(internal)* |
| `s3` | `minio/minio:latest` | Local S3-compatible file storage | `19000` / `19001` |
| `createbuckets` | `minio/mc` | One-shot bucket initializer | *(init only)* |
| `api` | Built from `Dockerfile` | FastAPI / uvicorn REST API | `18000` |
| `worker` | Built from `Dockerfile` | `arq` background task worker | *(internal)* |
| `setup` | Built from `Dockerfile` | Web onboarding wizard UI | `18080` |

All services have health checks. `api` and `worker` wait for `postgres`, `redis`, and `s3` to be healthy before starting.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Python 3.11+ (only needed for the optional CLI wizard step)

---

## First-Time Setup

### Step 1 — Create your `.env` file

```powershell
Copy-Item .env.example .env
```

Open `.env` and set at minimum:

| Variable | Required | Notes |
|---|---|---|
| `SESSION_SECRET` | **Yes** | Change from `test-secret` to a random string |
| `OPENAI_API_KEY` | Yes (for AI features) | OpenAI embeddings + LLM |
| `RESEND_API_KEY` | Optional | Transactional email; omit to disable email |
| `COHERE_API_KEY` | Optional | Reranking; omit to use OpenAI only |

All other variables have working defaults for local development (MinIO for S3, local Postgres/Redis).

### Step 2 — Create your `marketplace.yaml`

The API expects a `marketplace.yaml` configuration file. The quickest start is to copy the example:

```powershell
Copy-Item marketplace.example.yaml marketplace.yaml
```

For a guided setup, run the interactive CLI wizard instead (requires Python venv):

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
python -m cli wizard -o marketplace.yaml
```

### Step 3 — Build and start the stack

```powershell
docker compose up -d --build
```

On first run this will pull base images and build the app image — allow a few minutes.

### Step 4 — Run database migrations

> **Important:** The stack does not apply Alembic migrations automatically. Run this once after the first `up`, and after any schema-changing updates:

```powershell
docker compose exec api alembic upgrade head
```

### Step 5 — Bootstrap the first admin user

```powershell
$body = '{"email":"admin@example.com","password":"your-password"}'
Invoke-RestMethod -Method POST -Uri "http://localhost:18000/api/auth/bootstrap" `
  -ContentType "application/json" -Body $body
```

Or with curl (Git Bash / WSL2):

```bash
curl -sS -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}' | python -m json.tool
```

---

## Accessing the Services

| Service | URL |
|---|---|
| REST API + Swagger docs | `http://localhost:18000/docs` |
| API health check | `http://localhost:18000/api/health` |
| Setup / onboarding wizard | `http://localhost:18080/onboarding` |
| MinIO console (file storage) | `http://localhost:19001` (user: `minioadmin` / `minioadmin`) |

---

## Common Operations

```powershell
# View status of all services
docker compose ps

# Tail all logs
docker compose logs -f

# Tail API logs only
docker compose logs -f api

# Tail worker logs only
docker compose logs -f worker

# Stop the stack (preserves data volumes)
docker compose down

# Stop and wipe all data (full reset)
docker compose down -v --remove-orphans
```

---

## Updating After Code Changes

```powershell
# Rebuild and restart
docker compose up -d --build

# Re-run migrations if schema changed
docker compose exec api alembic upgrade head
```

---

## Windows Notes

The `Makefile` targets use bash syntax and will not run natively in PowerShell. Use the `docker compose` commands above directly, or run `make` targets via **Git Bash** or **WSL2**.

The `pyproject.toml` also defines equivalent `poe` tasks (e.g. `poe docker-up`, `poe docker-down`) that can be used when the Python venv is active.
