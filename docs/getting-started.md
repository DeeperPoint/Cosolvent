# Getting Started

## Prerequisites

- Python 3.11+
- MongoDB (running locally or remote)
- Redis (running locally or remote)
- AWS S3 bucket (for file uploads)
- OpenAI API key (for AI features)
- Pinecone account (for vector search)

## Installation

```bash
# Clone and install
git clone <repo-url>
cd cosolvent-beta
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Environment Configuration

Create a `.env` file in the project root:

```env
# Required
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=cosolvent
REDIS_URL=redis://localhost:6379
SESSION_SECRET=your-secret-key-here

# Optional — defaults shown
SESSION_TTL_HOURS=72
MARKETPLACE_CONFIG_PATH=marketplace.yaml
CORS_ORIGINS=["http://localhost:3000"]
DEBUG=false

# S3 (required for file uploads)
S3_BUCKET=cosolvent-files
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# AI services (required for AI features)
OPENAI_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=cosolvent
COHERE_API_KEY=

# Email (required for notifications)
RESEND_API_KEY=
EMAIL_FROM=noreply@example.com
```

## Creating a Marketplace Configuration

### Option 1: CLI Wizard (Interactive)

```bash
python -m cli wizard -o marketplace.yaml
```

The wizard walks through 7 steps:

1. **Marketplace Identity** — name, description, industry
2. **Participant Types** — 2–3 types with roles and permissions
3. **Profile Schemas** — field definitions per type
4. **Onboarding Workflows** — approval settings per type
5. **Communication Rules** — who can message whom
6. **Discovery Config** — search and filter settings
7. **Review & Generate** — confirm and write the file

### Option 2: Start from a Preset

```bash
# Agriculture marketplace (GrainPlaza)
python -m cli wizard --preset agriculture -o marketplace.yaml

# Professional services marketplace (ProConnect)
python -m cli wizard --preset professional_services -o marketplace.yaml
```

### Option 3: Copy the Example

```bash
cp marketplace.example.yaml marketplace.yaml
```

### Validating a Config File

```bash
python -m cli validate marketplace.yaml
```

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Bootstrapping an Admin User

Before using admin endpoints, create the first admin account:

```bash
curl -X POST http://localhost:8000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'
```

This endpoint only works when no admin users exist yet.

## Running Background Workers

Background jobs (document indexing, email sending, profile indexing) use Arq with Redis:

```bash
arq app.workers.settings.WorkerSettings
```

## Running Tests

```bash
pytest tests/unit/ -v
```
