# Background Workers

Cosolvent uses [ARQ](https://arq-docs.helpmanual.io/) for background task processing, backed by Redis as the job queue.

## Running the Worker

```bash
arq app.workers.settings.WorkerSettings
```

The worker runs as a separate process from the API server. It shares `.env` and all configuration with the API.

With Docker Compose, the worker starts automatically as the `worker` service.

## Worker Settings (`app/workers/settings.py`)

```python
class WorkerSettings:
    redis_settings = RedisSettings(...)   # from settings.redis_url
    functions = [
        process_document_task,
        index_profile_task,
        send_email_task,
    ]
```

## Registered Tasks

### `process_document_task`

**Location:** `app/workers/document_indexing.py`

**Triggered by:** `POST /api/ai/documents` (after document record is created)

**What it does:**
1. Retrieves the document record from the `ai_documents` collection
2. Splits text content into chunks
3. Generates embeddings for each chunk via `get_embeddings_batch()`
4. Upserts vectors into the `ai_document_chunks` table
5. Updates document status: `processing` → `indexed` (or `failed` on error)

**Failure behavior:** On exception, status is set to `"failed"`. Check `GET /api/admin/ai/documents` to see failed documents. Fix the underlying issue (usually a missing or invalid API key) and re-upload the document.

---

### `index_profile_task`

**Location:** `app/workers/profile_indexing.py`

**Triggered by:** Profile creation and profile status changes to `active`

**What it does:**
1. Retrieves the profile from the `profiles` collection
2. Extracts all searchable field values
3. Generates an embedding for the concatenated profile content
4. Upserts the vector into `profile_vectors` with metadata (participant type, status)
5. Marks the profile as indexed

This task keeps the vector search index in sync with active profiles. If a profile is updated or suspended, the task re-runs to update the embedding.

---

### `send_email_task`

**Location:** `app/workers/email_sender.py`

**Triggered by:**
- Profile approved (if `welcome_email_on_approval: true`)
- Profile rejected (sends feedback email)
- Other notification-worthy events

**What it does:**
1. Receives email parameters (to address, subject, body)
2. Sends via [Resend](https://resend.com) API using `RESEND_API_KEY`
3. Logs delivery result

**Requirements:** `RESEND_API_KEY` and `EMAIL_FROM` must be set. If `RESEND_API_KEY` is absent, the task logs a warning and exits without error — other tasks are unaffected.

---

## Enqueuing Jobs

Jobs are enqueued from the service layer:

```python
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

async def enqueue_document_task(doc_id: str):
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("process_document_task", doc_id=doc_id)
```

Job names must match the function names in `WorkerSettings.functions`.

---

## Retry Behavior

ARQ retries failed jobs with exponential backoff by default. Task-level retry settings can be configured in `WorkerSettings`. Currently all tasks use ARQ defaults.

---

## Running Locally Without the Worker

API endpoints that enqueue jobs work without the worker running — jobs are queued in Redis and processed when the worker starts. In development, you can skip the worker unless you need document indexing, profile vector search, or email sending.

---

## Debugging Worker Issues

### Worker not picking up jobs

```bash
docker compose logs worker
```

Check for Redis connection errors. Verify `REDIS_URL` in `.env` matches the Redis service.

### Document stuck in `processing`

The worker may have crashed before completing. Check worker logs for the exception. Common causes:
- Missing `OPENAI_API_KEY` (embedding generation failed)
- Invalid document content (empty or non-text)

### Profile search returning stale results

The `index_profile_task` may not have run after a profile update. Trigger it manually by making a minor profile update to re-queue the task.

---

## See Also
- [Architecture](architecture.md) — Redis in the system overview
- [AI Architecture](ai-architecture.md) — document and profile indexing details
- [Data Models](data-models.md) — `ai_document_chunks`, `profile_vectors`

---

[← AI Architecture](ai-architecture.md) · [API Reference →](api-reference.md)
