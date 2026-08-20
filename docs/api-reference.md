# API Reference

Base URL: `/api`

All endpoints return JSON. Authentication is via a `session_token` HTTP-only cookie, set automatically on signup/login — this is all a same-origin browser frontend needs.

**Cross-origin frontends** (a sponsor's own domain, native apps, server-to-server callers — GAP-1): the cookie may not be sent back on genuinely cross-site requests depending on browser SameSite/third-party-cookie policy. These callers should instead take the `access_token` returned in the signup/login/bootstrap response body and send it as `Authorization: Bearer <access_token>` on every request; the API accepts either credential (the header takes precedence when both are present). See `SESSION_COOKIE_SAMESITE` / `CORS_ORIGINS` in [environment-variables.md](environment-variables.md) for the matching cookie/CORS configuration.

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | Returns `{status: "ok", marketplace: "..."}` |

---

## Auth (`/api/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | None | Create account. Body: `{email, password, participant_type}` |
| POST | `/auth/login` | None | Login. Body: `{email, password}` |
| POST | `/auth/logout` | Required | Invalidate session, clear cookie |
| GET | `/auth/verify` | Required | Return current user info |
| POST | `/auth/bootstrap` | None | Create first admin. Body: `{email, password}`. Fails if admin exists. |

**Responses:** signup/login/bootstrap return `{user_id, email, participant_type, role, has_onboarded, access_token}` and set the `session_token` cookie. `access_token` is the same credential as the cookie, exposed for `Authorization: Bearer` use by cross-origin/native/server-to-server callers (GAP-1) — same-origin browser clients can ignore it.

---

## Profiles (`/api/profiles`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/profiles/{type_slug}/register` | Required | Register as participant type |
| GET | `/profiles/{type_slug}/draft` | Required | Get draft profile |
| PUT | `/profiles/{type_slug}/draft` | Required | Update draft fields. Body: `{fields: {...}}` |
| POST | `/profiles/{type_slug}/draft/submit` | Required | Submit draft for approval |
| GET | `/profiles/{type_slug}/me` | Required | Get own active profile |
| GET | `/profiles/{type_slug}/{profile_id}` | Optional | View profile (visibility-filtered) |
| PUT | `/profiles/{type_slug}/{profile_id}` | Required | Update own profile. Body: `{fields: {...}}` |
| POST | `/profiles/{type_slug}/{profile_id}/ai-generate` | Required | AI-generate profile content |
| POST | `/profiles/{type_slug}/{profile_id}/ai-approve` | Admin | Approve AI-generated profile |
| POST | `/profiles/{type_slug}/{profile_id}/ai-reject` | Admin | Reject AI-generated profile |

**Visibility tiers:** Anonymous users see `public` fields only. Authenticated users see `public` + `protected`. Profile owners and admins see all fields including `private`.

### Generated Role Alias Endpoints (`/api/roles`)

When project artifacts are generated, additive role-specific aliases are exposed (example for role `producer`):

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/roles/producer/register` | Required | Role-specific alias for register |
| GET | `/roles/producer/draft` | Required | Role-specific alias for draft |
| PUT | `/roles/producer/draft` | Required | Role-specific alias for draft update |
| POST | `/roles/producer/draft/submit` | Required | Role-specific alias for draft submit |
| GET | `/roles/producer/me` | Required | Role-specific alias for own profile |
| GET | `/roles/producer/{profile_id}` | Optional | Role-specific alias for profile view |
| PUT | `/roles/producer/{profile_id}` | Required | Role-specific alias for profile update |

---

## Files (`/api/files`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/files/upload` | Required | Upload file. Form: `file`, `privacy` (public/protected/private), `category`, `profile_id` |
| GET | `/files/{file_id}` | Required | Download file (checks visibility) |
| DELETE | `/files/{file_id}` | Required | Delete file (owner only) |

---

## Communication (`/api`)

### Conversations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/conversations` | Required | Start conversation. Body: `{receiver_user_id, initial_message}` |
| GET | `/conversations` | Required | List own conversations |
| GET | `/conversations/{conv_id}` | Required | Get conversation (must be participant) |
| POST | `/conversations/{conv_id}/accept` | Required | Accept pending request |
| POST | `/conversations/{conv_id}/reject` | Required | Reject request |
| POST | `/conversations/{conv_id}/close` | Required | Close conversation |

### Messages

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/conversations/{conv_id}/messages` | Required | List messages. Query: `skip`, `limit` |
| POST | `/conversations/{conv_id}/messages` | Required | Send message. Body: `{content, content_type}` |
| PUT | `/conversations/{conv_id}/messages/{msg_id}` | Required | Edit own message. Body: `{content}` |
| DELETE | `/conversations/{conv_id}/messages/{msg_id}` | Required | Delete own message |
| POST | `/conversations/{conv_id}/share-assets` | Required | Share files. Body: `{asset_ids: [...]}` |

### WebSocket

| Path | Description |
|------|-------------|
| `ws:///api/ws/{conversation_id}` | Real-time messaging. First message: `{type: "auth", token: "session_token"}` |

WebSocket message types: `"message"`, `"ping"`. Server broadcasts to all connected participants.

---

## Discovery (`/api/search`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/search` | Optional | Global search. Body: `{query, filters, page, page_size}` |
| POST | `/search/{type_slug}` | Optional | Search specific type. Body: `{query, filters, page, page_size}` |

Search combines keyword matching with vector similarity (when AI features are enabled). Results are visibility-filtered based on the caller's auth status.

---

## Notifications (`/api/notifications`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | Required | List notifications. Query: `skip`, `limit` |
| PUT | `/notifications/{notification_id}/read` | Required | Mark as read |

---

## AI (`/api/ai`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ai/query` | Required | RAG query. Body: `{query, thread_id?, filters?}` |
| POST | `/ai/follow-up` | Required | Get follow-up suggestions. Body: `{thread_id}` |
| POST | `/ai/documents` | Admin | Upload document. Body: `{filename, content}` |
| GET | `/ai/documents` | Admin | List documents. Query: `skip`, `limit` |
| DELETE | `/ai/documents/{doc_id}` | Admin | Delete document |
| GET | `/ai/models` | Admin | List available LLM models |
| GET | `/ai/settings` | Admin | Get LLM settings |
| PUT | `/ai/settings` | Admin | Update settings. Body: `{provider?, model?, temperature?, max_tokens?}` |
| GET | `/ai/prompts` | Admin | List prompt templates |
| PUT | `/ai/prompts/{intent}` | Admin | Update prompt. Body: `{template}` |

---

## Admin (`/api/admin`)

All admin endpoints require the `admin` role.

### Dashboard & Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/dashboard` | Aggregate stats (users, profiles, conversations, messages, pending apps) |
| GET | `/admin/config` | Current marketplace config summary |

### User Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List users. Query: `skip`, `limit` |
| GET | `/admin/users/{user_id}` | Get user details |
| PUT | `/admin/users/{user_id}/role` | Change role. Body: `{role: "user"|"admin"}` |
| POST | `/admin/users/{user_id}/deactivate` | Deactivate account |
| POST | `/admin/users/{user_id}/activate` | Reactivate account |

### Applications

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/applications` | List applications. Query: `status` |
| POST | `/admin/applications/{app_id}/approve` | Approve onboarding application |
| POST | `/admin/applications/{app_id}/reject` | Reject with feedback. Body: `{feedback?}` |

### Profile Override

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/profiles/{profile_id}` | Full profile (bypasses visibility filters) |
| PUT | `/admin/profiles/{profile_id}/status` | Change status. Body: `{status: "active"|"suspended"|"pending"}` |

### Conversation Oversight

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/conversations` | List all conversations. Query: `skip`, `limit`, `status` |
| GET | `/admin/conversations/{id}/messages` | Read any conversation's messages. Query: `skip`, `limit` |

### AI/LLM Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/ai/models` | Available LLM models |
| GET | `/admin/ai/settings` | Current LLM settings |
| PUT | `/admin/ai/settings` | Update settings. Body: `{provider?, model?, temperature?, max_tokens?}` |
| GET | `/admin/ai/prompts` | List prompt templates |
| PUT | `/admin/ai/prompts/{intent}` | Update prompt. Body: `{template}` |
| GET | `/admin/ai/documents` | List knowledge base documents. Query: `skip`, `limit` |
| DELETE | `/admin/ai/documents/{doc_id}` | Delete document from KB |

### FAQ Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/faqs` | List FAQs. Query: `active_only` |
| POST | `/admin/faqs` | Create FAQ. Body: `{question, answer, category?, sort_order?}` |
| GET | `/admin/faqs/{faq_id}` | Get FAQ |
| PUT | `/admin/faqs/{faq_id}` | Update FAQ. Body: `{question?, answer?, category?, sort_order?, is_active?}` |
| DELETE | `/admin/faqs/{faq_id}` | Delete FAQ |

---

## Setup/Onboarding (`/api/setup`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/setup/config-template` | None | Load current config template and source/runtime path metadata |
| POST | `/setup/validate` | None | Validate config payload |
| POST | `/setup/render-yaml` | None | Render validated YAML from config payload |
| POST | `/setup/save` | None | Save config YAML to output path and optionally apply in memory |
| POST | `/setup/generate` | None | Generate deterministic project artifacts + optional export archive |
| POST | `/setup/generate/check` | None | Verify generated artifacts are in sync with current config |
