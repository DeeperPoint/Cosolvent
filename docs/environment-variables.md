# Environment Variables

All settings are loaded from a `.env` file in the project root via Pydantic Settings (`app/core/config.py`).

## Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017` | Yes | MongoDB connection string |
| `MONGODB_DATABASE` | `cosolvent` | Yes | Database name |
| `REDIS_URL` | `redis://localhost:6379` | Yes | Redis connection string |
| `SESSION_SECRET` | `change-me` | Yes | Secret key for session token generation. **Change in production.** |
| `SESSION_TTL_HOURS` | `72` | No | Session expiry in hours |
| `S3_BUCKET` | `cosolvent-files` | For files | AWS S3 bucket name |
| `S3_REGION` | `us-east-1` | For files | AWS S3 region |
| `AWS_ACCESS_KEY_ID` | _(empty)_ | For files | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | _(empty)_ | For files | AWS secret key |
| `OPENAI_API_KEY` | _(empty)_ | For AI | OpenAI API key |
| `PINECONE_API_KEY` | _(empty)_ | For AI | Pinecone API key |
| `PINECONE_INDEX` | `cosolvent` | For AI | Pinecone index name |
| `COHERE_API_KEY` | _(empty)_ | For AI | Cohere API key |
| `RESEND_API_KEY` | _(empty)_ | For email | Resend email API key |
| `EMAIL_FROM` | `noreply@example.com` | For email | Sender email address |
| `MARKETPLACE_CONFIG_PATH` | `marketplace.yaml` | Yes | Path to marketplace YAML config |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | No | Allowed CORS origins (JSON array) |
| `DEBUG` | `false` | No | Enable debug logging |

## Minimal Development Setup

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=cosolvent
REDIS_URL=redis://localhost:6379
SESSION_SECRET=dev-secret-change-in-production
```

## Full Production Setup

```env
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net
MONGODB_DATABASE=cosolvent-prod
REDIS_URL=redis://redis-host:6379
SESSION_SECRET=long-random-secret-here
SESSION_TTL_HOURS=24

S3_BUCKET=my-marketplace-files
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret...

OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pc-...
PINECONE_INDEX=my-marketplace
COHERE_API_KEY=co-...

RESEND_API_KEY=re_...
EMAIL_FROM=noreply@my-marketplace.com

MARKETPLACE_CONFIG_PATH=marketplace.yaml
CORS_ORIGINS=["https://my-marketplace.com"]
DEBUG=false
```
