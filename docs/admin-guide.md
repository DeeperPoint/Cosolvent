# Admin Guide

The admin module provides a complete operations console for managing the marketplace. All admin endpoints live under `/api/admin/` and require the `admin` role.

## Getting Admin Access

### Bootstrap (First Admin)

When no admin users exist, create one via the bootstrap endpoint:

```bash
curl -X POST http://localhost:8000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "secure-password"}'
```

### Promoting Users

Existing admins can promote users:

```bash
curl -X PUT http://localhost:8000/api/admin/users/{user_id}/role \
  -H "Content-Type: application/json" \
  -b "session_token=..." \
  -d '{"role": "admin"}'
```

## Dashboard

`GET /api/admin/dashboard` returns aggregate marketplace stats:

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
Body: {"role": "admin"}  // or "user"
```

### Deactivate / Activate Users

```
POST /api/admin/users/{user_id}/deactivate
POST /api/admin/users/{user_id}/activate
```

Deactivated users receive a `403 Account deactivated` response on any authenticated request. This check uses `is False` (strict), so existing users without the `is_active` field are unaffected — no data migration required.

## Application Management

### List Applications

```
GET /api/admin/applications?status=pending
```

### Approve / Reject

```
POST /api/admin/applications/{app_id}/approve
POST /api/admin/applications/{app_id}/reject
Body: {"feedback": "Please provide more details about..."}  // optional
```

## Profile Override

Admins can view full profiles (bypassing visibility filters) and change profile status.

### View Full Profile

```
GET /api/admin/profiles/{profile_id}
```

Returns all fields including `private` ones, regardless of viewer tier.

### Change Profile Status

```
PUT /api/admin/profiles/{profile_id}/status
Body: {"status": "active"}  // or "suspended" or "pending"
```

## Conversation Oversight

Admins can browse all conversations and read messages without being a participant.

### List All Conversations

```
GET /api/admin/conversations?skip=0&limit=50&status=active
```

### Read Conversation Messages

```
GET /api/admin/conversations/{conversation_id}/messages?skip=0&limit=50
```

## AI/LLM Management

### View Available Models

```
GET /api/admin/ai/models
```

### View / Update LLM Settings

```
GET /api/admin/ai/settings

PUT /api/admin/ai/settings
Body: {"model": "gpt-4o", "temperature": 0.5, "max_tokens": 2048}
```

All fields are optional — only provided fields are updated.

### Manage Prompt Templates

```
GET /api/admin/ai/prompts

PUT /api/admin/ai/prompts/{intent}
Body: {"template": "You are a helpful assistant for {marketplace_name}..."}
```

### Knowledge Base Documents

```
GET /api/admin/ai/documents?skip=0&limit=50
DELETE /api/admin/ai/documents/{doc_id}
```

## FAQ Management

### List FAQs

```
GET /api/admin/faqs?active_only=true
```

FAQs are returned sorted by `sort_order`.

### Create FAQ

```
POST /api/admin/faqs
Body: {
  "question": "How do I register as a producer?",
  "answer": "Visit the signup page and select 'Producer' as your type...",
  "category": "Onboarding",
  "sort_order": 10
}
```

### Update FAQ

```
PUT /api/admin/faqs/{faq_id}
Body: {"answer": "Updated answer...", "is_active": false}
```

All fields are optional — only provided fields are updated.

### Delete FAQ

```
DELETE /api/admin/faqs/{faq_id}
```

## Configuration Summary

```
GET /api/admin/config
```

Returns the current marketplace configuration (participant types, communication rules, discovery settings) as JSON.
