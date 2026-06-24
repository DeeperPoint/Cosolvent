# How to Use Cosolvent

Cosolvent is a **config-driven marketplace builder**. You describe a marketplace in a
single `marketplace.yaml` (participant types, profile fields, discovery rules), and two
compilers turn it into a working backend (FastAPI + Postgres/pgvector) and frontend
(Next.js). This guide takes you from zero to a running marketplace.

> Two ways to get a `marketplace.yaml`:
> 1. **Author it** — interactive wizard, or hand-write/edit the YAML.
> 2. **Generate it from documents** — via the companion **CommonContext** repo (see
>    [Build from documents](#build-a-marketplace-from-documents) below and
>    `../CommonContext/HOW-TO-USE.md`).

---

## 1. Prerequisites

- **Python 3.12** and **Docker** (for the running stack).
- An **OpenRouter API key** (Claude is used to generate/enrich configs). Put it in
  `Cosolvent/.env`:
  ```
  OPENROUTER_API_KEY=sk-or-...
  # the OpenRouter key also powers embeddings for the Q&A knowledge library
  # (openai/text-embedding-3-small, 1536-dim). A direct OpenAI key is an optional fallback:
  # OPENAI_API_KEY=sk-...
  ```

Install backend deps:
```bash
cd Cosolvent
make install            # creates backend/.venv and installs everything
```

---

## 2. The pipeline at a glance

```
marketplace.yaml ──► compile ──► app/generated/*.py (routes, enums, policy) + OpenAPI + migration
       │                                   │
   (author or generate)                    ▼
                                   make up ──► live API at http://localhost:18000
```

Everything is driven by `marketplace.yaml`. Change it → recompile → restart.

---

## 3. Quick start (existing config)

```bash
cd Cosolvent

make validate-config   # check a marketplace.yaml is valid (defaults to marketplace.example.yaml)
make compile           # generate backend artifacts from marketplace.yaml
make up                # start the full stack: Postgres + Redis + API + worker
make wait-api          # wait until the API is healthy
```

Then open:
- API: `http://localhost:18000/api/`
- Swagger docs: `http://localhost:18000/docs`
- Onboarding UI: `http://localhost:18080/onboarding`

Stop / reset:
```bash
make down              # stop the stack
make reset             # stop AND drop the database volume (clean slate)
```

---

## 4. Author a marketplace

### Option A — interactive wizard
```bash
make wizard            # 7-step Q&A, writes marketplace.yaml
```

### Option B — generate from a domain schema (Claude)
```bash
# from a CommonContext domain schema → marketplace.yaml
make gen-config SCHEMA=../../CommonContext/schemas/machinery_trade_schema.yaml
#   override the output file:  GEN_OUT=../marketplace.machinery.yaml
#   override the model:        MODEL=anthropic/claude-sonnet-4.6
```

### Option C — hand-edit
Edit `marketplace.yaml` directly, then `make validate-config` + `make compile`.

---

## 5. Build a marketplace from documents

This is the end-to-end path that uses **both repos**: it turns the reference documents
in `CommonContext/inputs/` into a schema, a `marketplace.yaml`, a compiled backend, and
(optionally) a Q&A knowledge library — in one command.

```bash
cd Cosolvent
make build-from-docs           # optional: MODEL=anthropic/claude-sonnet-4.6
```

What it does:
1. **CommonContext**: convert every file in `inputs/` → Markdown, then synthesize one
   domain schema (`CommonContext/schemas/generated_schema.yaml`).
2. **CommonContext**: embed the docs → `generated_refs.jsonl` (using the same OpenRouter
   key — `openai/text-embedding-3-small`, 1536-dim).
3. **Cosolvent**: generate `marketplace.yaml` from that schema.
4. **Cosolvent**: compile the backend.
5. **Cosolvent**: load the knowledge library into `reference_library` *(if generated and
   the stack is running)*.

> The marketplace is built from **whatever is in `CommonContext/inputs/`**. For a
> machinery marketplace, keep only machinery documents there. See
> `../CommonContext/HOW-TO-USE.md`.

To serve the freshly built marketplace:
```bash
make reset && make up && make wait-api
```

---

## 6. Switch verticals (e.g. grain → machinery)

```bash
cd Cosolvent
make gen-config SCHEMA=../../CommonContext/schemas/machinery_trade_schema.yaml   # overwrites marketplace.yaml
make compile
make reset && make up && make wait-api      # reset drops the old DB (schemas differ)
```

---

## 7. Verify every API works

The stack ships an OpenAPI-driven smoke test that hits every documented endpoint and
flags any server error (5xx):

```bash
# with the stack running:
cd backend && .venv/bin/python scripts/api_smoke.py --base-url http://localhost:18000
```
A healthy result shows `"5xx": 0, "failures": []`. (4xx on auth-gated routes is expected
when no users are seeded.)

---

## 8. Frontend (optional)

```bash
make install-frontend
make generate-frontend     # generates a Next.js app from OpenAPI + marketplace.yaml
```

---

## 9. Common commands

| Command | What it does |
|---|---|
| `make install` | Set up `backend/.venv` |
| `make validate-config` | Validate a `marketplace.yaml` |
| `make wizard` | Interactive config builder |
| `make gen-config SCHEMA=...` | Generate `marketplace.yaml` from a schema (Claude) |
| `make build-from-docs` | Full build from `CommonContext/inputs/` (schema → marketplace → compile → knowledge) |
| `make compile` | Generate backend artifacts from `marketplace.yaml` |
| `make up` / `make down` / `make reset` | Start / stop / wipe the stack |
| `make wait-api` | Block until the API is healthy |
| `make logs-api` | Tail API logs |
| `make unit` | Run backend unit tests |

---

## 10. How the pieces relate

- **`marketplace.yaml`** — the single source of truth for the marketplace. Compiled into
  `backend/app/generated/`.
- **CommonContext** — the companion content/curation repo. It turns reference documents
  into (a) the **domain schema** that feeds `marketplace.yaml`, and (b) the **knowledge
  library** that feeds the runtime Q&A `reference_library`. See
  `../CommonContext/HOW-TO-USE.md`.

```
CommonContext docs ─► schema ─► marketplace.yaml ─► compile ─► Cosolvent APIs
                  └─► embeddings ─► reference_library ─► Q&A endpoint
```
