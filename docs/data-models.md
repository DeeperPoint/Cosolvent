# Data Models

Cosolvent uses MongoDB for all persistent storage. Collections are accessed via Motor (async driver). Indexes are created automatically at startup in `app/core/database.py`.

## Collections

### `users`

Stores user accounts.

```json
{
  "_id": "ObjectId",
  "email": "user@example.com",
  "password_hash": "bcrypt hash",
  "role": "user | admin",
  "participant_type": "producer",
  "is_active": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Indexes:** `email` (unique)

### `sessions`

Active user sessions.

```json
{
  "_id": "ObjectId",
  "token": "random session token",
  "user_id": "ObjectId (ref: users)",
  "expires_at": "datetime",
  "created_at": "datetime"
}
```

**Indexes:** `token` (unique), `expires_at` (TTL — auto-deleted after expiry)

### `profiles`

Participant profiles (also serve as marketplace listings).

```json
{
  "_id": "ObjectId",
  "user_id": "string (ref: users)",
  "participant_type": "producer",
  "status": "draft | pending | active | suspended",
  "fields": {
    "farm_name": "Green Valley Farm",
    "country": "Canada",
    "primary_crops": ["Wheat", "Barley"]
  },
  "ai_profile": "AI-generated description (optional)",
  "completeness": 85,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Indexes:** `user_id`, `participant_type`, compound `(participant_type, status)`

### `drafts`

In-progress profile drafts (one per user).

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "participant_type": "producer",
  "status": "draft",
  "fields": { "...": "..." },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Indexes:** `user_id` (unique)

### `applications`

Onboarding approval requests.

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "participant_type": "producer",
  "draft_id": "string (ref: drafts)",
  "status": "pending | approved | rejected",
  "admin_feedback": "string (optional)",
  "created_at": "datetime"
}
```

**Indexes:** `user_id`, `status`

### `conversations`

Messaging conversations between participants.

```json
{
  "_id": "ObjectId",
  "participants": [
    {"user_id": "string", "accepted_at": "datetime"}
  ],
  "status": "pending | active | closed",
  "created_at": "datetime"
}
```

**Indexes:** `participants.user_id`, `status`

### `messages`

Individual messages within conversations.

```json
{
  "_id": "ObjectId",
  "conversation_id": "string (ref: conversations)",
  "sender_id": "string (ref: users)",
  "content": "Hello, I'm interested in your wheat...",
  "content_type": "text | image | video | audio | file",
  "created_at": "datetime",
  "edited_at": "datetime (optional)"
}
```

**Indexes:** `conversation_id`, compound `(conversation_id, created_at)`

### `files`

Uploaded file metadata (actual files stored in S3).

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "filename": "certificate.pdf",
  "s3_key": "uploads/abc123/certificate.pdf",
  "content_type": "application/pdf",
  "privacy": "public | protected | private",
  "category": "document",
  "profile_id": "ObjectId (optional, ref: profiles)",
  "created_at": "datetime"
}
```

**Indexes:** `user_id`, `profile_id`

### `private_assets`

Private files that can be shared in conversations.

**Indexes:** `user_id`

### `notifications`

User notification records.

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "type": "conversation_request | message | approval",
  "title": "New conversation request",
  "body": "Buyer XYZ wants to connect",
  "is_read": false,
  "created_at": "datetime"
}
```

**Indexes:** `user_id`, compound `(user_id, is_read)`

### `faqs`

Admin-managed FAQ entries.

```json
{
  "_id": "ObjectId",
  "question": "How do I register?",
  "answer": "Visit the signup page...",
  "category": "Onboarding",
  "sort_order": 10,
  "is_active": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Indexes:** `is_active`, `sort_order`

### `ai_documents`

Knowledge base documents for RAG.

**Indexes:** `status`

### `ai_chat_history`

RAG conversation threads.

**Indexes:** `user_id`, `thread_id`

## Serialization Pattern

All modules use the same `_serialize()` helper to convert MongoDB documents for API responses:

```python
def _serialize(doc: dict) -> dict:
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
```

This converts `_id` (ObjectId) to `id` (string) and returns a plain dict.
