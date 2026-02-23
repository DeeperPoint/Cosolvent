# API Reference

Base URL: `/api`. All endpoints return JSON.

**Authentication:** `session_token` HTTP-only cookie, set automatically on signup/login. Pass it as a cookie header: `-b "session_token=..."`.

**Auth requirements in this reference:**
- **None** — public endpoint, no authentication required
- **Optional** — works without auth; results differ based on visibility tier
- **Required** — must be authenticated as any user
- **Admin** — must be authenticated as a user with `role: "admin"`

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | Returns `{"status": "ok", "marketplace": "<name>"}` |

---

## Auth (`/api/auth`)

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| POST | `/api/auth/signup` | None | `{email, password, participant_type}` | Create account and session |
| POST | `/api/auth/login` | None | `{email, password}` | Login, returns session |
| POST | `/api/auth/logout` | Required | — | Invalidate session, clear cookie |
| GET | `/api/auth/verify` | Required | — | Return current user info |
| POST | `/api/auth/bootstrap` | None | `{email, password}` | Create first admin. Fails if admin exists. |

**Signup / Login response:**

```json
{
  "session_token": "...",
  "user": {"id": "...", "email": "...", "role": "user", "participant_type": "producer"}
}
```

---

## Profiles (`/api/profiles`)

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| POST | `/api/profiles/{type_slug}/register` | Required | — | Register user as participant type |
| GET | `/api/profiles/{type_slug}/draft` | Required | — | Get own draft profile |
| PUT | `/api/profiles/{type_slug}/draft` | Required | `{fields: {...}}` | Update draft field values |
| POST | `/api/profiles/{type_slug}/draft/submit` | Required | — | Submit draft for approval |
| GET | `/api/profiles/{type_slug}/me` | Required | — | Get own active profile |
| GET | `/api/profiles/{type_slug}/{profile_id}` | Optional | — | View profile (visibility-filtered) |
| PUT | `/api/profiles/{type_slug}/{profile_id}` | Required | `{fields: {...}}` | Update own active profile |
| POST | `/api/profiles/{type_slug}/{profile_id}/ai-generate` | Required | — | AI-generate profile content from documents |
| POST | `/api/profiles/{type_slug}/{profile_id}/ai-approve` | Admin | — | Approve AI-generated profile draft |
| POST | `/api/profiles/{type_slug}/{profile_id}/ai-reject` | Admin | — | Reject AI-generated profile draft |

**Profile response (visibility-filtered):**

```json
{
  "id": "...",
  "participant_type": "producer",
  "status": "active",
  "fields": {"farm_name": "Sunrise Farm", "country": "Canada"},
  "completeness": 80
}
```

Fields returned depend on the viewer tier (anonymous → public fields only, authenticated → + protected, owner/admin → + private).

### Generated Role Alias Endpoints (`/api/roles`)

After generating artifacts, role-specific alias routes are available. Example for a `producer` role:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/roles/producer/register` | Required | Alias for `/api/profiles/producer/register` |
| GET | `/api/roles/producer/draft` | Required | Alias for draft |
| PUT | `/api/roles/producer/draft` | Required | Alias for draft update |
| POST | `/api/roles/producer/draft/submit` | Required | Alias for draft submit |
| GET | `/api/roles/producer/me` | Required | Alias for own profile |
| GET | `/api/roles/producer/{profile_id}` | Optional | Alias for profile view |
| PUT | `/api/roles/producer/{profile_id}` | Required | Alias for profile update |

---

## Files (`/api/files`)

| Method | Path | Auth | Request | Description |
|--------|------|------|---------|-------------|
| POST | `/api/files/upload` | Required | Form: `file`, `privacy`, `category?`, `profile_id?` | Upload file to S3 |
| GET | `/api/files/{file_id}` | Required | — | Download file (visibility checked) |
| DELETE | `/api/files/{file_id}` | Required | — | Delete file (owner only) |

**Privacy values:** `public`, `private` (controlled by `FILES_ALLOWED_PRIVACY` env var).

---

## Communication (`/api`)

### Conversations

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| POST | `/api/conversations` | Required | `{receiver_user_id, initial_message}` | Start conversation |
| GET | `/api/conversations` | Required | — | List own conversations |
| GET | `/api/conversations/{conv_id}` | Required | — | Get conversation details |
| POST | `/api/conversations/{conv_id}/accept` | Required | — | Accept pending request |
| POST | `/api/conversations/{conv_id}/reject` | Required | — | Reject request |
| POST | `/api/conversations/{conv_id}/close` | Required | — | Close conversation |

### Messages

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| GET | `/api/conversations/{conv_id}/messages` | Required | Query: `skip`, `limit` | List messages |
| POST | `/api/conversations/{conv_id}/messages` | Required | `{content, content_type}` | Send message |
| PUT | `/api/conversations/{conv_id}/messages/{msg_id}` | Required | `{content}` | Edit own message |
| DELETE | `/api/conversations/{conv_id}/messages/{msg_id}` | Required | — | Delete own message |
| POST | `/api/conversations/{conv_id}/share-assets` | Required | `{asset_ids: [...]}` | Share private files |

### WebSocket

| Path | Description |
|------|-------------|
| `ws://host/api/ws/{conversation_id}` | Real-time messaging channel |

**Protocol:**
1. Connect to WebSocket URL
2. Send auth: `{"type": "auth", "token": "<session_token>"}`
3. Send messages: `{"type": "message", "content": "..."}`
4. Keepalive: `{"type": "ping"}` → server responds `{"type": "pong"}`

Server broadcasts all messages to all connected participants in the conversation.

---

## Discovery (`/api/search`)

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| POST | `/api/search` | Optional | `{query, filters, page, page_size}` | Global search across all searchable types |
| POST | `/api/search/{type_slug}` | Optional | `{query, filters, page, page_size}` | Search specific participant type |

**Request:**

```json
{
  "query": "organic wheat producers in Canada",
  "filters": {"country": "Canada"},
  "page": 1,
  "page_size": 20
}
```

Results are visibility-filtered based on authentication status. Anonymous search requires `anonymous_search_enabled: true` in config.

---

## Notifications (`/api/notifications`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/notifications` | Required | List notifications. Query: `skip`, `limit` |
| PUT | `/api/notifications/{notification_id}/read` | Required | Mark as read |

---

## AI (`/api/ai`)

| Method | Path | Auth | Request body | Description |
|--------|------|------|-------------|-------------|
| POST | `/api/ai/query` | Required | `{query, thread_id?, filters?}` | RAG query with optional thread context |
| POST | `/api/ai/follow-up` | Required | `{thread_id}` | Get follow-up query suggestions |
| POST | `/api/ai/documents` | Admin | `{filename, content}` | Upload document to knowledge base |
| GET | `/api/ai/documents` | Admin | Query: `skip`, `limit` | List knowledge base documents |
| DELETE | `/api/ai/documents/{doc_id}` | Admin | — | Delete document |
| GET | `/api/ai/models` | Admin | — | List available LLM models |
| GET | `/api/ai/settings` | Admin | — | Get current LLM settings |
| PUT | `/api/ai/settings` | Admin | `{provider?, model?, temperature?, max_tokens?}` | Update LLM settings |
| GET | `/api/ai/prompts` | Admin | — | List prompt templates |
| PUT | `/api/ai/prompts/{intent}` | Admin | `{template}` | Update prompt template |

**AI query response:**

```json
{
  "answer": "Based on the available information...",
  "thread_id": "...",
  "sources": [{"chunk_id": "...", "text": "..."}]
}
```

---

## Admin (`/api/admin`)

All admin endpoints require `role: "admin"`.

### Dashboard & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/dashboard` | Aggregate stats |
| GET | `/api/admin/config` | Current marketplace config summary |

### User Management

| Method | Path | Request body | Description |
|--------|------|-------------|-------------|
| GET | `/api/admin/users` | Query: `skip`, `limit` | List users |
| GET | `/api/admin/users/{user_id}` | — | User details |
| PUT | `/api/admin/users/{user_id}/role` | `{role: "user"\|"admin"}` | Change role |
| POST | `/api/admin/users/{user_id}/deactivate` | — | Deactivate account |
| POST | `/api/admin/users/{user_id}/activate` | — | Reactivate account |

### Applications

| Method | Path | Request body | Description |
|--------|------|-------------|-------------|
| GET | `/api/admin/applications` | Query: `status` | List applications |
| POST | `/api/admin/applications/{app_id}/approve` | — | Approve application |
| POST | `/api/admin/applications/{app_id}/reject` | `{feedback?}` | Reject with optional feedback |

### Profile Override

| Method | Path | Request body | Description |
|--------|------|-------------|-------------|
| GET | `/api/admin/profiles/{profile_id}` | — | Full profile (bypasses visibility) |
| PUT | `/api/admin/profiles/{profile_id}/status` | `{status: "active"\|"suspended"\|"pending"}` | Change profile status |

### Conversation Oversight

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/conversations` | List all conversations. Query: `skip`, `limit`, `status` |
| GET | `/api/admin/conversations/{id}/messages` | Read any conversation's messages. Query: `skip`, `limit` |

### AI/LLM Management

| Method | Path | Request body | Description |
|--------|------|-------------|-------------|
| GET | `/api/admin/ai/models` | — | Available LLM models |
| GET | `/api/admin/ai/settings` | — | Current LLM settings |
| PUT | `/api/admin/ai/settings` | `{provider?, model?, temperature?, max_tokens?}` | Update settings |
| GET | `/api/admin/ai/prompts` | — | Prompt templates |
| PUT | `/api/admin/ai/prompts/{intent}` | `{template}` | Update prompt |
| GET | `/api/admin/ai/documents` | Query: `skip`, `limit` | Knowledge base documents |
| DELETE | `/api/admin/ai/documents/{doc_id}` | — | Delete document |

### FAQ Management

| Method | Path | Request body | Description |
|--------|------|-------------|-------------|
| GET | `/api/admin/faqs` | Query: `active_only` | List FAQs (sorted by sort_order) |
| POST | `/api/admin/faqs` | `{question, answer, category?, sort_order?}` | Create FAQ |
| GET | `/api/admin/faqs/{faq_id}` | — | Get FAQ |
| PUT | `/api/admin/faqs/{faq_id}` | `{question?, answer?, category?, sort_order?, is_active?}` | Update FAQ |
| DELETE | `/api/admin/faqs/{faq_id}` | — | Delete FAQ |

---

## Setup/Onboarding (`/api/setup`)

Used by the wizard UI. Not part of the production API.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/setup/config-template` | None | Load current config (falls back to example) |
| GET | `/api/setup/presets` | None | List available marketplace presets |
| POST | `/api/setup/validate` | None | Validate config payload |
| POST | `/api/setup/render-yaml` | None | Render config as YAML text |
| POST | `/api/setup/save` | None | Validate + write config to disk |
| POST | `/api/setup/generate` | None | Run full compiler pipeline |
| POST | `/api/setup/generate/check` | None | Dry-run sync check (no writes) |

---

## Error Responses

All errors follow:

```json
{
  "detail": "Error message"
}
```

Or for validation errors:

```json
{
  "detail": {
    "message": "Config validation failed",
    "errors": [{"loc": [...], "msg": "...", "type": "..."}]
  }
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request / validation error |
| 401 | Not authenticated |
| 403 | Forbidden (wrong role or deactivated account) |
| 404 | Resource not found |
| 503 | AI service unavailable (no provider configured) |

---

## See Also
- [Modules](modules.md) — module-level behavior details
- [Admin Guide](../user/admin-guide.md) — admin API usage guide
- [AI Features](../user/ai-features.md) — AI endpoint setup
