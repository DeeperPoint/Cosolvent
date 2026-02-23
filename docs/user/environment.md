# Environment Variables

All settings are loaded from `.env` via `app/core/config.py`. Copy `.env.example` to `.env` before running for the first time.

## Minimal Local Setup

```env
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/cosolvent
REDIS_URL=redis://localhost:6379
SESSION_SECRET=dev-secret-change-in-production
MARKETPLACE_CONFIG_PATH=marketplace.yaml
```

## Full Reference

### Database (Postgres)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `POSTGRES_DSN` | _(empty)_ | Yes, or use discrete vars below | Full SQLAlchemy async DSN, e.g. `postgresql+asyncpg://user:pass@host:5432/db`. When set, discrete `POSTGRES_*` vars are ignored. |
| `POSTGRES_HOST` | `localhost` | If `POSTGRES_DSN` absent | Postgres hostname |
| `POSTGRES_PORT` | `5432` | If `POSTGRES_DSN` absent | Postgres port |
| `POSTGRES_DB` | `cosolvent` | If `POSTGRES_DSN` absent | Database name |
| `POSTGRES_USER` | `postgres` | If `POSTGRES_DSN` absent | Database user |
| `POSTGRES_PASSWORD` | `postgres` | If `POSTGRES_DSN` absent | Database password |

> **Warning:** Your Postgres deployment must allow `CREATE EXTENSION IF NOT EXISTS vector;`. The `pgvector` extension is required for AI-powered search. If running locally, install it with your Postgres package manager.

### Redis

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Yes | Redis connection string. Used for session storage and the ARQ job queue. |

### Session

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `SESSION_SECRET` | `change-me` | Yes | Secret key for session token generation. Change this before any non-local deployment. |
| `SESSION_TTL_HOURS` | `72` | No | Session expiry in hours. Sessions older than this value are invalidated. |

> **Warning:** `SESSION_SECRET=change-me` is the default and must be changed before production. Leaked sessions are permanent if the secret is not rotated.

### File Storage (S3)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `S3_BUCKET` | `cosolvent-files` | For file uploads | S3 bucket name |
| `S3_REGION` | `us-east-1` | For file uploads | AWS region for the bucket |
| `AWS_ACCESS_KEY_ID` | _(empty)_ | For file uploads | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | _(empty)_ | For file uploads | AWS secret access key |
| `FILES_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | No | Maximum allowed upload size in bytes |
| `FILES_PRIVATE_URL_TTL_SECONDS` | `300` (5 min) | No | Expiry time for presigned URLs on private files |
| `FILES_ALLOWED_PRIVACY` | `["public","private"]` | No | JSON array of accepted file privacy values |

File upload endpoints return errors if S3 credentials are missing. Non-file flows continue normally.

### AI Providers

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OPENAI_API_KEY` | _(empty)_ | For OpenAI | OpenAI API key. Required for OpenAI models and embeddings. |
| `OPENROUTER_API_KEY` | _(empty)_ | For OpenRouter | OpenRouter API key. For routing to many models via a single endpoint. |
| `GEMINI_API_KEY` | _(empty)_ | For Gemini | Google Gemini API key. |
| `COHERE_API_KEY` | _(empty)_ | Optional | Cohere API key for reranking search results (enhances discovery quality). |

AI endpoints return `503 Service Unavailable` when no provider is configured. All non-AI flows continue normally without any API key.

See [AI Features](ai-features.md) for provider setup instructions.

### Email

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RESEND_API_KEY` | _(empty)_ | For email jobs | Resend API key. Required for welcome emails and approval notifications. |
| `EMAIL_FROM` | `noreply@example.com` | For email jobs | Sender email address used for all outbound email. |

Email jobs are enqueued by the background worker. They silently fail if `RESEND_API_KEY` is not set.

### Application

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MARKETPLACE_CONFIG_PATH` | `marketplace.yaml` | Yes | Path to your `marketplace.yaml` file. Can be relative (to the project root) or absolute. |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | No | JSON array of allowed CORS origins for the API. Add your frontend URL here. |
| `DEBUG` | `false` | No | Enable debug logging. Set to `true` for verbose output during development. |

---

## Docker Compose Behavior

When running with `docker compose`, environment variables from your `.env` file are passed into the containers automatically. The `POSTGRES_DSN`, `REDIS_URL`, and service hostnames are pre-configured in `docker-compose.yml` to point to the correct internal container names — you typically only need to set `SESSION_SECRET` and any AI/email keys.

---

## See Also
- [Quick Start](quick-start.md) — minimal setup to get running
- [Running](running.md) — Docker Compose and local startup details
- [AI Features](ai-features.md) — AI provider configuration

---

[← Marketplace Config Reference](marketplace-config.md) · [Running Cosolvent →](running.md)
