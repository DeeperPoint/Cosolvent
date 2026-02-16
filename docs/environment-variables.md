# Environment Variables

All settings are loaded from `.env` via `app/core/config.py`.

## Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `POSTGRES_DSN` | _(empty)_ | Yes (or discrete `POSTGRES_*`) | SQLAlchemy async DSN, e.g. `postgresql+asyncpg://...` |
| `POSTGRES_HOST` | `localhost` | If `POSTGRES_DSN` absent | Postgres host |
| `POSTGRES_PORT` | `5432` | If `POSTGRES_DSN` absent | Postgres port |
| `POSTGRES_DB` | `cosolvent` | If `POSTGRES_DSN` absent | Database name |
| `POSTGRES_USER` | `postgres` | If `POSTGRES_DSN` absent | DB user |
| `POSTGRES_PASSWORD` | `postgres` | If `POSTGRES_DSN` absent | DB password |
| `REDIS_URL` | `redis://localhost:6379` | Yes | Redis connection string |
| `SESSION_SECRET` | `change-me` | Yes | Secret for session token generation (change in production) |
| `SESSION_TTL_HOURS` | `72` | No | Session expiry in hours |
| `S3_BUCKET` | `cosolvent-files` | For files | S3 bucket |
| `S3_REGION` | `us-east-1` | For files | S3 region |
| `AWS_ACCESS_KEY_ID` | _(empty)_ | For files | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | _(empty)_ | For files | AWS secret |
| `FILES_MAX_UPLOAD_BYTES` | `26214400` | No | Maximum allowed upload size (bytes) |
| `FILES_PRIVATE_URL_TTL_SECONDS` | `300` | No | Presigned URL TTL for private file reads |
| `FILES_ALLOWED_PRIVACY` | `["public","private"]` | No | JSON array of accepted privacy values |
| `OPENAI_API_KEY` | _(empty)_ | For AI endpoints | OpenAI API key |
| `COHERE_API_KEY` | _(empty)_ | Optional | Cohere rerank key |
| `RESEND_API_KEY` | _(empty)_ | For email jobs | Resend API key |
| `EMAIL_FROM` | `noreply@example.com` | For email jobs | Sender email |
| `MARKETPLACE_CONFIG_PATH` | `marketplace.yaml` | Yes | Marketplace YAML config path |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | No | JSON array of allowed origins |
| `DEBUG` | `false` | No | Debug logging toggle |

## Minimal Local Setup

```env
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/cosolvent
REDIS_URL=redis://localhost:6379
SESSION_SECRET=dev-secret-change-in-production
MARKETPLACE_CONFIG_PATH=marketplace.yaml
```

## Production Note

Your Postgres deployment must allow:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
