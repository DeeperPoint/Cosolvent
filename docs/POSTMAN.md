# Postman collections

## Option A — Import the generated collection (recommended)

A Postman Collection v2.1 file is generated from the same OpenAPI schema as `/docs`:

| File | Description |
|------|-------------|
| `postman/Cosolvent-API.postman_collection.json` | All HTTP routes, grouped by OpenAPI tag |

**Regenerate after API changes:**

```bash
make postman-export
```

Or:

```bash
.venv/bin/python scripts/export_postman_collection.py --out postman/Cosolvent-API.postman_collection.json
```

**Import in Postman:** **Import** → choose `postman/Cosolvent-API.postman_collection.json`.

**Variables:**

- `baseUrl` — default **`http://localhost:18000`** (collection → **Variables** tab). Every request uses `{{baseUrl}}/api/...` in the URL `raw` field so it resolves correctly. Do not leave `baseUrl` empty.

**If JSON bodies look empty:** regenerate the collection with a current `main` branch — older exports did not resolve OpenAPI `$ref` schemas. Run:

` .venv/bin/python scripts/export_postman_collection.py --out postman/Cosolvent-API.postman_collection.json `

**If URLs look empty or “no route”:** the collection sets `protocol`, `host`, `port`, and `path` on every request (not only `raw`). Ensure **Collection → Variables → `baseUrl`** is `http://localhost:18000` (no trailing slash). Re-import the latest `postman/Cosolvent-API.postman_collection.json` if you have an older file.

**Authentication:**

The API uses a **`session_token` cookie** (not returned in the JSON body). After **Login**:

1. Run **POST** `/api/auth/login` with email/password.
2. Copy `session_token` from the response **Headers** → `Set-Cookie`, **or** use Postman’s **Cookies** for `localhost` (may require HTTPS for `Secure` cookies in some clients).
3. For other requests, add header: `Cookie: session_token=<value>`.

**Profile registration without a prior session:**

`POST` `/api/profiles/{type}/register` and `POST` `/api/roles/{role}/register` — **no** session cookie. Response: **`{ "status": "pending_review", "application_id": "..." }`**.

- **JSON:** `Content-Type: application/json` with **`email`** and **`fields`** (object).
- **Multipart (same URL):** `Content-Type: multipart/form-data` with form fields **`email`** (text), **`fields`** (text containing a **JSON object** string), and one or more **`files`** (or **`file`**) parts for onboarding documents. Up to **10** files; each must respect the global upload size limit.
- Gated by **`auth.allow_public_application`** (or **`ALLOW_PUBLIC_APPLICATION`**), separate from **`auth.allow_public_signup`**.
- **Admin** approves (`POST /api/admin/applications/{id}/approve`): user + profile are created, files are moved to the new profile, and credentials are emailed when email is configured.
- **Session already present** — use **`application/json`** only with **`{ "fields": { ... } }`** (multipart is rejected when authenticated).

---

## Option B — Import OpenAPI directly in Postman

With the API running:

1. Postman → **Import** → **Link**.
2. Enter: `http://localhost:18000/openapi.json`
3. Postman will create a collection from the live schema.

Use the same cookie/session notes as above.

---

## WebSockets

Real-time messaging uses **WebSocket**, not REST. It does not appear in this Postman collection. Connect to:

`ws://localhost:18000/api/ws/{conversation_id}`

(see `app/modules/communication/router.py`).
