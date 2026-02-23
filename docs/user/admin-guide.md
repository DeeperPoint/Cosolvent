# Admin Guide

The admin API provides a complete operations console for managing your marketplace. All endpoints require the `admin` role and are prefixed with `/api/admin/`.

## Getting Admin Access

### Bootstrap (First Admin)

When no admin users exist, use the bootstrap endpoint to create the first one:

```bash
curl -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "ChangeMe123!"}'
```

Or via Make:

```bash
make bootstrap-admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=ChangeMe123!
```

This endpoint fails if an admin already exists. Call it only once.

### Promoting Existing Users

Existing admins can promote other users:

```bash
curl -X PUT http://localhost:18000/api/admin/users/{user_id}/role \
  -H "Content-Type: application/json" \
  -b "session_token=YOUR_TOKEN" \
  -d '{"role": "admin"}'
```

---

## Dashboard

Get aggregate marketplace statistics:

```
GET /api/admin/dashboard
```

Returns:

```json
{
  "total_users": 150,
  "active_profiles": 120,
  "pending_applications": 5,
  "total_conversations": 80,
  "total_messages": 1200,
  "profiles_by_type": {"producer": 60, "buyer": 60},
  "marketplace": {
    "name": "GrainPlaza",
    "industry": "Specialty Agriculture",
    "participant_types": ["producer", "buyer"]
  }
}
```

---

## User Management

### List Users

```
GET /api/admin/users?skip=0&limit=50
```

### View User Details

```
GET /api/admin/users/{user_id}
```

Returns all user fields except `password_hash`.

### Change User Role

```
PUT /api/admin/users/{user_id}/role
Body: {"role": "admin"}   // or "user"
```

### Deactivate / Reactivate

```
POST /api/admin/users/{user_id}/deactivate
POST /api/admin/users/{user_id}/activate
```

Deactivated users receive `403 Account deactivated` on any authenticated request. Reactivation restores full access.

---

## Application Management

When participant types require admin approval (`requires_approval: true`), submitted profiles become applications that need review.

### List Applications

```
GET /api/admin/applications?status=pending
```

Supported statuses: `pending`, `approved`, `rejected`.

### Approve

```
POST /api/admin/applications/{app_id}/approve
```

Approving creates an active profile for the user. If `welcome_email_on_approval: true` is set for that participant type, a welcome email is sent (requires `RESEND_API_KEY`).

### Reject

```
POST /api/admin/applications/{app_id}/reject
Body: {"feedback": "Please provide more details about your farming operation."}
```

The `feedback` field is optional. If provided, it is delivered to the user.

---

## Profile Override

### View Full Profile

```
GET /api/admin/profiles/{profile_id}
```

Returns all fields including `private` ones, bypassing all visibility filters. Useful for reviewing complete profile data during moderation.

### Change Profile Status

```
PUT /api/admin/profiles/{profile_id}/status
Body: {"status": "active"}   // or "suspended" or "pending"
```

Use `suspended` to temporarily deactivate a live profile without rejecting the application.

---

## Conversation Oversight

Admins can read any conversation without being a participant.

### List All Conversations

```
GET /api/admin/conversations?skip=0&limit=50&status=active
```

### Read Messages

```
GET /api/admin/conversations/{conversation_id}/messages?skip=0&limit=50
```

---

## AI/LLM Settings

Configure the AI provider and model used for all AI-powered features (RAG queries, profile generation, embeddings).

### View Available Models

```
GET /api/admin/ai/models
```

Returns models from the currently configured provider.

### View Settings

```
GET /api/admin/ai/settings
```

Returns current LLM settings including provider, model, temperature, and max_tokens.

### Update Settings

```
PUT /api/admin/ai/settings
Body: {
  "provider": "openai",
  "model": "gpt-4o",
  "temperature": 0.5,
  "max_tokens": 2048
}
```

All fields are optional — only provided fields are updated. Changes take effect immediately (no restart required).

**Supported providers:** `openai`, `openrouter`, `gemini`

See [AI Features](ai-features.md) for provider-specific setup and model recommendations.

---

## Prompt Templates

Customize the system prompts used by the AI for different tasks.

### List Prompt Templates

```
GET /api/admin/ai/prompts
```

### Update a Template

```
PUT /api/admin/ai/prompts/{intent}
Body: {"template": "You are a helpful assistant for {marketplace_name}..."}
```

The `{marketplace_name}` placeholder is replaced at runtime. Available intents depend on which AI features are enabled in your marketplace config.

---

## Knowledge Base Documents

Upload documents to the RAG knowledge base. These are chunked and indexed as embeddings, then used to answer user queries.

### List Documents

```
GET /api/admin/ai/documents?skip=0&limit=50
```

### Upload a Document

```
POST /api/ai/documents
Body: {"filename": "producer-guide.pdf", "content": "<text content>"}
```

Document processing (chunking and embedding) happens asynchronously in the background worker. Check the document's `status` field: `processing` → `indexed` (or `failed`).

### Delete a Document

```
DELETE /api/admin/ai/documents/{doc_id}
```

Deletes the document and all associated embedding chunks.

---

## FAQ Management

Create and manage FAQ entries visible to users.

### List FAQs

```
GET /api/admin/faqs?active_only=true
```

Returned in `sort_order` order.

### Create FAQ

```
POST /api/admin/faqs
Body: {
  "question": "How do I register as a producer?",
  "answer": "Visit the signup page and select Producer as your type...",
  "category": "Onboarding",
  "sort_order": 10
}
```

### Update FAQ

```
PUT /api/admin/faqs/{faq_id}
Body: {"answer": "Updated answer...", "is_active": false}
```

All fields are optional.

### Delete FAQ

```
DELETE /api/admin/faqs/{faq_id}
```

---

## Marketplace Config Summary

```
GET /api/admin/config
```

Returns the current marketplace configuration (participant types, communication rules, discovery settings) as JSON. Useful for verifying what is active at runtime.

---

## See Also
- [AI Features](ai-features.md) — setting up providers and RAG
- [Troubleshooting](troubleshooting.md) — common admin issues
- [FAQ](faq.md) — frequent operator questions
