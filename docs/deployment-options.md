# Cosolvent — Operation & Deployment Options

Decision aid for operating and deploying a generated Cosolvent marketplace beyond the
local dev stack. Derived from `docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`, `docs/architecture.md`, and `docs/setup-guide-technical.md`.

**Near-term goal on record:** stand up an **internal demo / pilot URL** for a single
vertical. The recommended path for that goal is **Section 4 (Option B — Managed PaaS)**.

---

## 1. What you're actually deploying

Cosolvent is **single-tenant-per-vertical**: each marketplace is one `marketplace.yaml`
compiled into **deterministic generated artifacts** that are baked per config. "Deploy a
marketplace" therefore means *build images from that vertical's config and stand up its
backing services*.

| Piece | What it is | Stateful? | Weight |
|---|---|---|---|
| **backend** image | FastAPI `api` + `arq` `worker` + `setup` wizard (one image, three commands) | no | light (`python:3.11-slim`, **no torch**) |
| **frontend** image | Next.js; **compiles the UI at build time** from `marketplace.yaml` + `openapi/generated_openapi.json` | no | light |
| **Postgres + pgvector** | operational tables + vector search (`profile_vectors`, `ai_document_chunks`, `reference_library`) | **yes** | — |
| **Redis** | `arq` job queue (async indexing, doc processing, email) | yes (ephemeral) | — |
| **Object storage** | uploaded files; minio locally, any S3 via `S3_ENDPOINT_URL` | **yes** | — |
| **Compile pipeline** | CommonContext docs→schema→`marketplace.yaml`→compile | build-time only | **heavy** (torch/CUDA via `marker-pdf`) |

**Critical distinction:** the runtime is light and uses OpenRouter/OpenAI **API calls** for
embeddings + RAG. The GPU-heavy torch/`marker-pdf` stack runs **only in the offline build**,
never in production containers. **Your deploy targets do not need GPUs.**

---

## 2. Operating model

- **Single-tenant-per-vertical (recommended, matches design).** Each marketplace = its own
  deployment (images compiled from its `marketplace.yaml`, its own database). Clean isolation,
  per-vertical scaling/cost, aligns with the "compile to deterministic deployable assets" thesis.
- **Multi-tenant (one runtime, many marketplaces)** would be a significant re-architecture —
  generated artifacts are baked per config. Not recommended now.
- **Where config comes from:** either the offline CLI (`python -m cli wizard/compile`) or the
  in-product **setup/onboarding wizard** (`/onboarding`, the `setup` service). For deployments,
  treat `marketplace.yaml` as a build input checked into the vertical's repo/branch.

---

## 3. Must-fix before *any* production target

The current `docker-compose.yml` is **local-dev**, not production: it bind-mounts source
(`./:/project`), uses `SESSION_SECRET: test-secret`, default `postgres/postgres`, and minio
credentials. Before deploying anywhere:

1. **Bake artifacts into images (#1 gap).** `backend/Dockerfile` does **not** COPY
   `app/generated/`, `marketplace.yaml`, `openapi/`, or `generated/` — in dev they're
   bind-mounted. For real images, run `compile` *then* `docker build` so the generated
   marketplace is inside the image (or COPY those paths explicitly).
2. **Migrations on deploy.** `alembic upgrade head` is manual today; make it a
   release/predeploy step. The generated `auto_marketplace_*.py` migration is baked per build.
3. **Secrets.** Real `SESSION_SECRET`; non-default DB creds; runtime keys:
   `OPENROUTER_API_KEY`/`OPENAI_API_KEY` (embeddings + RAG), `RESEND_API_KEY` (email),
   S3 credentials. Use the platform's secret store, never commit them.
4. **Postgres must have pgvector** (Render, Fly, Supabase, Neon, Cloud SQL, RDS all support it).
5. **Object storage** → Cloudflare R2 or AWS S3. Trivial: the app already honors
   `S3_ENDPOINT_URL`, so R2 works by pointing the endpoint + creds at it.
6. **Worker stays always-on** — don't put the `arq` worker on scale-to-zero.
7. **CORS + cookies** — set `CORS_ORIGINS` to the real frontend domain; ensure session
   cookies are `Secure` over HTTPS.
8. **CI** — add the `compile --check` drift gate (the "CI contract" in `architecture.md`) and
   image build/push to the existing lint/unit workflow.

---

## 4. Options

### Option A — Single VM + docker-compose (prod override)
- **Stack:** one cloud VM (Hetzner / DigitalOcean / Lightsail), a `docker-compose.prod.yml`
  override (built images, **no** bind mounts, real secrets), Caddy or Traefik for TLS.
- **Pros:** lowest cost (~€5–15/mo), simplest, closest to the current compose, full control.
- **Cons:** you own backups/patching/uptime; single point of failure; DB on the same box is risky.
- **Fit:** a throwaway internal demo box, or one pilot where you accept the ops burden.

### Option B — Managed PaaS  ★ recommended for the pilot-URL goal
- **Stack:** **Render** or **Fly.io**. `api` = web service, `worker` = background worker,
  `frontend` = web service, **managed Postgres with pgvector**, managed Redis
  (Render Key Value / Upstash), Cloudflare R2 for files. Deploy from the two Dockerfiles;
  run migrations as a release/predeploy command.
- **Pros:** low ops, git-push deploys, TLS + managed DB backups handled, env-var secrets.
  A real HTTPS URL fast. Per-vertical = a separate app group / environment.
- **Cons:** per-service cost adds up across `api`+`worker`+`frontend` × verticals; Redis add-on
  cost; mild platform lock-in.
- **Fit:** **a few verticals / pilots with minimal ops** — the sweet spot for a small team.

### Option C — Serverless containers
- **Stack:** **Cloud Run** (api + frontend, scale-to-zero) or **ECS Fargate / App Runner**;
  Cloud SQL / RDS Postgres (pgvector); **Upstash** Redis (Memorystore/ElastiCache aren't
  serverless); GCS / S3; worker as a `min-instances=1` service.
- **Pros:** cheapest **at idle** (scale-to-zero) — ideal for many low-traffic verticals; managed
  everything; Terraform-able; scales up under load.
- **Cons:** more initial setup (IaC, Cloud SQL connector, networking); cold starts; the worker
  can't scale to zero.
- **Fit:** multiple sleepy verticals where idle cost matters and you'll invest setup once.

### Option D — Kubernetes (GKE/EKS + Helm)
- Overkill now. Only at many tenants with a dedicated ops function. Noted as the future ceiling.

| | A. VM + compose | B. Managed PaaS ★ | C. Serverless | D. Kubernetes |
|---|---|---|---|---|
| Ops burden | High | Low | Medium | Very high |
| Cost | Lowest | Low–med | Cheapest at idle | High |
| Scaling | Manual | Auto-ish | Auto + scale-to-zero | Full |
| Best for | Demo / 1 pilot | **A few verticals** | Many low-traffic verticals | Many tenants + ops team |
| Main watch-out | DB on same box | per-service × N cost | worker min-instances=1; Upstash for Redis | overkill now |

---

## 5. Recommended path for a pilot URL (Option B)

Concrete sequence to get one vertical to a public HTTPS URL with minimal ops (Render shown;
Fly.io is equivalent with `fly postgres` providing pgvector):

1. **Make images self-contained** (the must-fix #1): a build step that runs
   `python -m cli compile --config marketplace.yaml --mode mvp`, then `docker build` so
   `app/generated/`, `marketplace.yaml`, `openapi/`, `generated/` are baked in.
2. **Provision managed services:** Render Postgres (enable `pgvector`), Render Key Value
   (or Upstash) for Redis, a Cloudflare R2 bucket.
3. **Create three services** from the repo: `api` (`uvicorn app.main:app`),
   `worker` (`arq app.workers.settings.WorkerSettings`), `frontend` (Next.js image).
4. **Set env/secrets** per service: `POSTGRES_DSN`, `REDIS_URL`, `SESSION_SECRET` (random),
   `OPENROUTER_API_KEY`, `RESEND_API_KEY`, `S3_*` + `S3_ENDPOINT_URL` (R2),
   `CORS_ORIGINS` (frontend URL), `MARKETPLACE_CONFIG_PATH`.
5. **Run migrations on release:** `alembic upgrade head` as the `api` service's predeploy command.
6. **Bootstrap the first admin:** `POST /api/auth/bootstrap` (see `docker-readme.md`), since
   public signup is off by default.
7. **Smoke test:** `/api/health` returns the marketplace name; Swagger at `/docs`; the frontend
   loads the compiled UI.

**Cheaper alternative for a strictly internal demo:** Option A on a small VM with Caddy for
automatic TLS — one `docker-compose.prod.yml`, no managed-service bills.

---

## 6. Future engineering work (when you move past a single pilot)

- CI builds + pushes per-vertical images (GHCR), gated by `compile --check`.
- Parameterize builds by `marketplace.yaml` so a new vertical = a new build, not new code.
- Move to Option C (Cloud Run + Cloud SQL + Upstash) when idle cost across verticals matters.
- Backups/restore runbook for Postgres; object-storage lifecycle policy.

---

*Related:* [`windows-build-gotchas.md`](windows-build-gotchas.md) ·
[`TEST-COSOLVENT_AND COMMONCONTEXT.md`](../TEST-COSOLVENT_AND%20COMMONCONTEXT.md) ·
[`docs/architecture.md`](architecture.md)
