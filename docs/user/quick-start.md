# Quick Start

Get from a fresh clone to a running marketplace in about 10 minutes using Docker.

## Prerequisites

- Docker and Docker Compose
- Git

No Python or database setup required for the Docker path.

## The Five Steps

```
Clone → Configure → Generate → Boot → Admin
```

---

## Step 1 — Clone

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
cp .env.example .env
```

> **Tip:** Open `.env` and change `SESSION_SECRET` to a random value before running anything else. Everything else can stay at its default for local testing.

---

## Step 2 — Configure your marketplace

Start the setup service (a lightweight container that serves only the wizard):

```bash
make setup-up
```

Open the wizard in your browser:

```
http://localhost:18080/onboarding
```

Work through the 7-step wizard:
1. Choose a starting template (or start blank)
2. Set your marketplace name, industry, and description
3. Define participant types and their permissions
4. Set onboarding and approval rules per type
5. Define communication rules (who contacts whom)
6. Configure profile fields and discovery settings
7. Review, validate, and click **Generate Project**

The wizard saves `marketplace.yaml` and compiles all artifacts before you leave.

> **Tip:** If you are unsure about any setting, the presets (Agriculture, B2B Services, Manufacturing) provide sensible defaults — you can always reconfigure later.

After generating, stop the setup service:

```bash
make setup-down
```

---

## Step 3 — Boot the full stack

```bash
make up
make wait-api
```

`make up` starts the API server, background worker, Postgres, and Redis. `make wait-api` polls until the API is healthy (up to 3 minutes).

Expected output from `make wait-api`:

```
Waiting for http://localhost:18000/api/health ...
✓ Ready
```

The API is now available at:
- API: `http://localhost:18000`
- Swagger docs: `http://localhost:18000/docs`

---

## Step 4 — Bootstrap first admin

```bash
make bootstrap-admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=ChangeMe123!
```

Or directly:

```bash
curl -X POST http://localhost:18000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'
```

This creates the first admin account. The endpoint fails if an admin already exists — it is safe to call only once.

---

## Step 5 — Verify

```bash
curl http://localhost:18000/api/health
```

Expected:

```json
{"status": "ok", "marketplace": "Your Marketplace Name"}
```

Visit `http://localhost:18000/docs` to see your API, including any generated role-specific routes (e.g. `/api/roles/producer/register`).

---

## Stopping the Stack

```bash
make down
```

To also remove volumes (database data):

```bash
docker compose down -v
```

---

## Re-running After Config Changes

After editing `marketplace.yaml` (or re-running the wizard):

1. Open the wizard and generate again — or run `make compile` directly
2. Restart the stack: `make down && make up && make wait-api`

The compiler is deterministic: the same config always produces the same artifacts.

---

## Port Conflicts

If port `18000` is already in use:

```bash
API_HOST_PORT=19000 docker compose up -d --build
```

Then use `http://localhost:19000` instead.

---

## Optional: Validate Config Without Starting

```bash
python -m cli validate marketplace.yaml
python -m cli compile --check --config marketplace.yaml --mode mvp
```

`validate` checks the YAML schema. `compile --check` verifies that generated artifacts match the current config.

---

## See Also
- [Setup Wizard](setup-wizard.md) — full wizard walkthrough with every field explained
- [Marketplace Config Reference](marketplace-config.md) — every YAML option
- [Environment Variables](environment.md) — what goes in `.env`
- [Running](running.md) — Docker Compose details, logs, health checks
