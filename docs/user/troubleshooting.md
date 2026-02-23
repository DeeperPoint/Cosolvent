# Troubleshooting

Common issues and their solutions, organized by symptom.

## Startup Failures

### API container exits immediately

Check logs:

```bash
docker compose logs api
```

**Common causes:**

- `marketplace.yaml` not found — ensure `MARKETPLACE_CONFIG_PATH` points to an existing file. Run `make setup-up` and complete the wizard if you have not yet generated the config.
- Config validation error at startup — run `python -m cli validate marketplace.yaml` to see the specific error.
- DB connection refused — Postgres may still be starting. Wait 10–15 seconds and retry `make up`.

---

### `marketplace.yaml` validation error on startup

```bash
python -m cli validate marketplace.yaml
```

Read the per-field errors and fix them. Common causes:
- `select`/`multi_select` field with no `options` defined
- `searchable_types` references a type slug that doesn't exist
- `filter_fields` references a field key that isn't in any profile schema
- `rag_strict` mode with `vector_search_enabled: false`

---

### `pgvector` extension error

```
ERROR: extension "vector" is not available
```

Your Postgres instance does not have `pgvector` installed. If using the Docker Compose setup, this should be handled automatically. If using an external Postgres, run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

You may need superuser privileges. Contact your database administrator if using a managed service (some plans don't allow custom extensions).

---

## Port Conflicts

### Port 18000 already in use

```bash
API_HOST_PORT=19000 docker compose up -d --build
```

Use `http://localhost:19000` for all API calls.

### Port 18080 (wizard) already in use

Edit `docker-compose.yml` and change the setup service port mapping:

```yaml
setup:
  ports:
    - "18090:18080"
```

Then access the wizard at `http://localhost:18090/onboarding`.

---

## Database Errors

### Migration fails on startup

```bash
docker compose logs api | grep -i alembic
```

If the migration failed due to a schema conflict, check whether the `auto_marketplace_*` migration was applied correctly. Run:

```bash
docker compose exec api python -m alembic history
docker compose exec api python -m alembic current
```

If stuck, you may need to drop and recreate the database (only safe in development):

```bash
docker compose down -v
make up
```

---

### `unique constraint violation` on startup

This can happen if the API is started before Postgres is ready and the app inserts duplicate setup data. Stop and restart:

```bash
docker compose down
make up
make wait-api
```

---

## Worker Not Processing

### Documents stay in `processing` status

The worker is likely not running or not connected to Redis.

```bash
docker compose logs worker
```

Check for:
- Redis connection errors
- Missing `OPENAI_API_KEY` (document indexing requires embeddings)
- Unhandled exceptions in the worker log

Restart the worker:

```bash
docker compose restart worker
```

---

### Email not sending

- Check `RESEND_API_KEY` is set in `.env`
- Check `EMAIL_FROM` is a valid sender address authorized in your Resend account
- Check worker logs for email task failures: `docker compose logs worker`

---

## AI Endpoints Return 503

`503 Service Unavailable` from any `/api/ai/*` endpoint means no AI provider is configured or the provider is unreachable.

1. Check that an API key is set in `.env`:
   ```bash
   grep -E "OPENAI|OPENROUTER|GEMINI" .env
   ```

2. Check that the provider is configured via the admin API:
   ```bash
   curl http://localhost:18000/api/admin/ai/settings \
     -b "session_token=YOUR_TOKEN"
   ```

3. Verify the API key is valid by testing it directly with the provider's API.

4. Restart the API after updating `.env`:
   ```bash
   docker compose restart api
   ```

Non-AI flows (auth, profiles, search, conversations) continue normally without AI.

---

## Wizard Issues

### Wizard won't load

- Check the setup service is running: `docker compose logs setup`
- Verify `make setup-up` completed without errors
- Try a hard refresh in the browser (Ctrl+Shift+R / Cmd+Shift+R)

### Config won't validate in the wizard

Open browser devtools (F12) → Network → look for failed requests to `/api/setup/validate`. The `detail.errors` array in the response contains Pydantic errors with `loc` (path) and `msg` (message).

Common fixes:
- Remove empty sections from profile schemas
- Add `options` to any `select`/`multi_select` field
- Make sure at least one participant type has both `can_search: true` and one has `visible_in_search: true`

### Generate hangs or fails

```bash
docker compose logs setup
```

If the compiler throws an error, it appears in the setup service logs. Most compile errors are configuration errors that also fail `validate`.

---

## Compile Drift Error in CI

```
CI gate: generated artifacts are out of sync
```

Your generated artifacts (`app/generated/`, migration, OpenAPI spec) don't match the current `marketplace.yaml`.

Fix by regenerating:

```bash
make compile
git add app/generated/ alembic/versions/auto_marketplace_*.py openapi/generated_openapi.json generated/manifest.json
git commit -m "Regenerate artifacts"
```

---

## Session / Auth Issues

### `401 Not authenticated` after login

Sessions are stored in Redis with a configurable TTL (default 72 hours). If Redis restarted, sessions are lost. Log in again.

### Bootstrap endpoint returns `400 Admin already exists`

The first admin has already been created. Use the login endpoint instead:

```bash
curl -X POST http://localhost:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "YourPassword"}'
```

---

## See Also
- [Running](running.md) — Docker Compose details
- [Environment Variables](environment.md) — all env var defaults and requirements
- [FAQ](faq.md) — quick answers to common questions

---

[← AI Features](ai-features.md) · [FAQ →](faq.md)
