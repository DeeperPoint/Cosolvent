# Operations Runbook

How to provision, run and verify a marketplace twin. This document covers the
operational surface: standing an instance up, loading a population, rebuilding
the match cache, and confirming the result.

For configuration semantics see `marketplace-configuration.md`; for the HTTP
surface see `api-reference.md`.

## Prerequisites

| Component | Requirement |
|---|---|
| Python | 3.11, with the backend virtualenv installed |
| PostgreSQL | 16 with the `pgvector` extension |
| Redis | 7 |
| Embeddings | An API key for the configured provider |

## Environment

An instance is defined by its database and its marketplace contract. Everything
else has a working default.

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=cosolvent
export REDIS_URL=redis://localhost:6379
export MARKETPLACE_CONFIG_PATH=../marketplace.yaml
export SYNTHETIC_WATERMARK_SECRET=<shared with the population generator>
```

`SYNTHETIC_WATERMARK_SECRET` must match the secret used to sign the population.
Records whose watermark does not verify are rejected at import.

`DEMO_MODE` selects the instance's staging:

| Value | Behaviour |
|---|---|
| `off` | Normal marketplace. Writes allowed, live AI. |
| `showcase` | Read-only. Serves the precomputed cache; no database writes. |
| `live` | Writes allowed, sessions ephemeral. Enables persona sign-in. |
| `full` | Fully stateful, including the acknowledgment lifecycle. |

See `environment-variables.md` for the complete list.

## Running two markets from one checkout

Instances differ only in which database and which contract they load, so a
second market needs no second deployment:

```bash
POSTGRES_DB=market_a MARKETPLACE_CONFIG_PATH=../marketplace-a.yaml \
  python -m uvicorn app.main:app --port 18000

POSTGRES_DB=market_b MARKETPLACE_CONFIG_PATH=../marketplace-b.yaml \
  python -m uvicorn app.main:app --port 18001
```

The generated role aliases under `app/generated/` are compiled from one
marketplace. When an instance loads a contract whose participant types do not
match the compiled ones, those aliases are skipped and a warning naming both
sets is written to the log; the generic `/api/profiles/{type_slug}` routes serve
that instance. Recompile to regenerate aliases for a different market.

## Database migrations

Run before first start and after any upgrade:

```bash
cd backend && alembic upgrade head
```

`alembic heads` must report a single head.

## Provisioning

`provision-twin` runs six stages — preflight, configure, knowledge, contract,
population, precompute:

```bash
python -m cli provision-twin --config ../marketplace.yaml \
  --population population-signed.json
```

Stages may be skipped when re-running against an instance that is already
configured:

```bash
python -m cli provision-twin --config ../marketplace.yaml \
  --population population-signed.json --skip configure,knowledge
```

Each stage reports its own result. A population stage reports counts for loaded,
updated, indexed, rejected (watermark) and skipped (invalid) records; a
precompute stage reports personas, match sets and cached answers.

## Loading a population

Populations are JSON documents of watermarked records, loaded through the
population stage above or the ingest API. Import verifies every watermark,
writes the profile, and indexes its embedding.

Loading several participant types is a sequence of runs, one per file. Each run
re-runs precompute, so the cache reflects the full population after the last.

## Rebuilding the match cache

Precompute scores every valid pairing and writes the results the
participant-facing screens read. It is admin-triggered:

```bash
curl -X POST http://localhost:8000/api/admin/showcase/run \
  -b "session_token=..."
```

Each run records a run entry and a ledger row per scored pairing. The cache
holds the latest result only; the ledger retains the history, so a score that
changes between runs remains visible.

## Verifying an instance

Confirm the instance is serving the expected market:

```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/showcase/market
curl -s http://localhost:8000/api/showcase/runs
```

`/api/showcase/market` returns the participant types with their role kinds,
field definitions and per-role permissions, without a session. `/api/showcase/runs`
returns precompute runs newest first, each with the counts it produced.

Per participant type and persona:

```bash
curl -s "http://localhost:8000/api/showcase/personas/{type}?limit=30"
curl -s "http://localhost:8000/api/showcase/personas/{type}/{id}/matches"
curl -s "http://localhost:8000/api/showcase/personas/{type}/{id}/ledger"
```

## Activity record

Market and profile events are recorded append-only. Market-level events are
public; a profile's own trail is readable by its owner or an admin.

```bash
curl -s http://localhost:8000/api/activity/public
```

## Serving the participant screens

The front end is a static bundle that reads the API over CORS. The API's
allowed origins are configured with `CORS_ORIGINS`; the origin serving the
bundle must appear in that list.

Serve the bundle with a threaded static server. A single-threaded server stalls
on the browser's concurrent requests for the page's scripts.

## Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| Startup fails on config | `MARKETPLACE_CONFIG_PATH` resolves to a missing file | Path is relative to the working directory; use an absolute path or start from `backend/` |
| Log warns that role aliases were skipped | Compiled aliases belong to another marketplace | Expected when running a second market; recompile to regenerate |
| Import reports rejected records | Watermark did not verify | Confirm `SYNTHETIC_WATERMARK_SECRET` matches the generator's |
| Screens show no data | Precompute has not run for this instance | Trigger a precompute run and re-check `/api/showcase/runs` |
| Browser requests fail with a CORS error | Serving origin not in the allowlist | Add it to `CORS_ORIGINS` and restart |
| `alembic heads` reports more than one head | Divergent migration branches | Merge the heads before upgrading |
