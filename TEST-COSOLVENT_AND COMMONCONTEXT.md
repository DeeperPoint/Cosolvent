# Build & Test the Generated Cosolvent APIs

End-to-end: drop documents in, build the marketplace, and verify the generated
backend APIs (including the knowledge library) actually work.

All commands run from `~/cosolvent_beta/Cosolvent` unless noted.

---

## 1. Add your documents

Put the files that describe the market into CommonContext's inputs folder:

```
~/cosolvent_beta/CommonContext/inputs/
```

Supported: PDFs, CSV/XLSX, and web pages saved as files. The marketplace is built
from **whatever is in this folder** — keep only the documents for the vertical you want.

> Tip: to start clean, move unrelated files out of `inputs/` first.

---

## 2. Set the AI key (one-time prerequisite)

Stage 1 reads the docs with an LLM and creates embeddings, so a key must be set.
Put it in `~/cosolvent_beta/Cosolvent/.env` (or `CommonContext/.env`):

```
OPENROUTER_API_KEY=sk-or-...      # powers schema synthesis + embeddings
# OPENAI_API_KEY=sk-...           # optional fallback for embeddings only
```

Without an embedding key the APIs still build, but the knowledge library is empty
(so the §5 knowledge test will return nothing).

---

## 3. Build everything and go live — one command

```bash
make live-from-docs
```

This runs the full pipeline in the correct order:

1. **schema + knowledge library** from `inputs/`
2. **`marketplace.yaml`** generated from the schema
3. **compile** the backend API artifacts from `marketplace.yaml`
4. **fresh stack** up (`reset` → `up` → `wait-api`)
5. **load the knowledge library** into the running database

It finishes with: `LIVE — open Swagger at http://localhost:18000/docs`.

> ⚠️ `make live-from-docs` runs `reset`, which **wipes the database**. That's correct
> for rebuilding from new docs; don't run it against data you want to keep.
> Override the AI model with `make live-from-docs MODEL=anthropic/claude-opus-4.8`.

**To rebuild after changing documents:** repeat steps 1 and 3.
**To reload only the knowledge library** (stack already up): `make load-knowledge`.

---

## 4. Test the APIs — the interactive way (recommended)

Open **Swagger** in a browser on the same machine:

```
http://localhost:18000/docs
```

You'll see every generated endpoint. The list reflects your `marketplace.yaml` —
e.g. role endpoints for **buyer / seller / service_provider**. Expand any endpoint,
click **Try it out**, fill the fields, and **Execute** to call it live.

Good first calls, in order:
1. `POST /api/auth/signup` → create a user
2. `POST /api/auth/login` → start a session (Swagger keeps the cookie)
3. `POST /api/profiles/{type_slug}/register` → create a profile (try `type_slug` = `seller`)
4. `POST /api/search` → run discovery/matching
5. `POST /api/ai/knowledge` → query the knowledge library (see §5)

---

## 5. Test from the terminal (quick smoke checks)

**Is the API healthy?**
```bash
curl -s http://localhost:18000/api/health
```

**How many endpoints were generated?**
```bash
curl -s http://localhost:18000/openapi.json \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin)['paths']), 'endpoints')"
```

**Query the knowledge library** (this proves the loaded documents are searchable).
Only `query` is required; `vertical` should match your build (e.g. `machinery_trade`):
```bash
curl -s -X POST http://localhost:18000/api/ai/knowledge \
  -H "Content-Type: application/json" \
  -d '{"query": "What standards apply to precision machining?", "top_k": 5, "vertical": "machinery_trade"}'
```
You should get back relevant chunks from your documents. If it returns `401`,
the endpoint needs a session — log in first and reuse the cookie:
```bash
# log in, saving the session cookie to a file
curl -s -c cookies.txt -X POST http://localhost:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'

# then send the cookie with the knowledge query
curl -s -b cookies.txt -X POST http://localhost:18000/api/ai/knowledge \
  -H "Content-Type: application/json" \
  -d '{"query": "What standards apply to precision machining?", "vertical": "machinery_trade"}'
```

> The exact request fields for any endpoint are shown in Swagger (`/docs`) — use it
> as the source of truth for request bodies.

---

## 6. Test with the automated test suites

With the stack running:

```bash
make integration     # hits the live API (integration tests)
make e2e             # full-stack end-to-end tests
```

Or generate a Postman collection to explore/test by hand:

```bash
make postman-export                 # writes postman/Cosolvent-API.postman_collection.json
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Swagger won't load | Step 3 hasn't finished — wait for "API is ready", then refresh. |
| `make live-from-docs` stops mentioning an API key | Set `OPENROUTER_API_KEY` (§2). |
| `/api/ai/knowledge` returns empty | No embedding key at build time, or run `make load-knowledge` while the stack is up. |
| `database "cosolvent" does not exist` | A local Postgres on `:5432` is shadowing the Docker one on `:15432`. The Makefile pins the DSN to `:15432`; if running the CLI by hand, set `POSTGRES_DSN=...localhost:15432/cosolvent`. |
| Endpoints look stale after editing `marketplace.yaml` | Re-run `make compile` then `make reset && make up && make wait-api`. |
