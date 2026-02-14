# Background Workers

Cosolvent uses [Arq](https://arq-docs.helpmanual.io/) for background task processing, backed by Redis as the job queue.

## Running Workers

```bash
arq app.workers.settings.WorkerSettings
```

Workers run as a separate process from the API server. They share the same `.env` configuration.

## Registered Tasks

### `process_document_task`

**Location:** `app/workers/document_indexing.py`

Triggered when a document is uploaded to the knowledge base via `POST /api/ai/documents`.

**What it does:**
1. Retrieves the document from MongoDB
2. Chunks the content into segments
3. Generates embeddings via OpenAI
4. Upserts vectors into Pinecone
5. Updates document status in MongoDB

### `index_profile_task`

**Location:** `app/workers/profile_indexing.py`

Triggered when a profile is created or updated.

**What it does:**
1. Retrieves the profile from MongoDB
2. Extracts searchable fields
3. Generates embedding for profile content
4. Upserts vector into Pinecone
5. Marks profile as indexed

### `send_email_task`

**Location:** `app/workers/email_sender.py`

Triggered on events requiring email notification.

**What it does:**
1. Receives email parameters (to, subject, body)
2. Sends via Resend API
3. Logs delivery result

**Trigger events:**
- Profile approved (welcome email, if `welcome_email_on_approval: true`)
- Profile rejected (feedback email)
- Other notification-worthy events

## Configuration

Worker settings are defined in `app/workers/settings.py`:

```python
class WorkerSettings:
    redis_settings = RedisSettings(...)
    functions = [
        process_document_task,
        index_profile_task,
        send_email_task,
    ]
```

## Enqueuing Jobs

Jobs are enqueued from the service layer:

```python
from arq import create_pool
from app.core.config import settings

pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
await pool.enqueue_job("process_document_task", doc_id=doc_id)
```
