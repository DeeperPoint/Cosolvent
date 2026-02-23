# FAQ

Quick answers to frequent questions from marketplace operators.

---

**Q: What is the difference between `supply`, `demand`, and `facilitator` role types?**

`supply` is for the side that provides the good or service (e.g. Producer, Service Provider). `demand` is for the side that seeks it (e.g. Buyer, Client). `facilitator` is for intermediary roles that operate the platform or mediate transactions. Role type is mostly semantic today — it appears in admin panels and helps you reason about the permission matrix. Permissions are what actually controls behavior.

---

**Q: When should I require approval for a participant type?**

Require approval for supply-side types when profile quality matters — you want to verify credentials, certifications, or content before a profile goes live. Auto-approve demand-side types to reduce activation friction. A typical setup: manual approval for producers/providers, auto-approve for buyers/clients.

---

**Q: Can I add more than 3 participant types?**

No, the current MVP limit is 2–3 participant types. This constraint exists because the permission matrix, communication rules, and UI complexity grow quickly with more types. Most B2B marketplaces work well with two types and an optional facilitator.

---

**Q: Can I change my config after generation?**

Yes. Edit `marketplace.yaml` (or re-run the wizard), then run `make compile` and restart the stack. New fields are added without data loss. However:
- Changing a participant type **slug** is breaking — it changes API paths and requires the old slug to be remapped everywhere.
- Removing a participant type requires manual data migration for existing profiles.
- Changing field **names** is also breaking for existing profile data.

---

**Q: What happens to existing data when I recompile?**

The compiler regenerates code and creates a new database migration for marketplace metadata tables. It does not touch operational data (users, profiles, conversations, etc.). The metadata migration is idempotent — safe to run multiple times.

---

**Q: Do I have to use Docker?**

No. See [Running — Local Development](running.md) for setup without Docker. You need Python 3.11+, Postgres with pgvector, and Redis.

---

**Q: What is the compile-check command for?**

```bash
python -m cli compile --check --config marketplace.yaml --mode mvp
```

This is a CI gate. It verifies that the generated artifacts in `app/generated/`, the Alembic migration, and the OpenAPI spec all match the current `marketplace.yaml`. If you manually edit the config without regenerating, this check fails. Use `make compile` to regenerate.

---

**Q: Why do AI endpoints return 503?**

Either no AI provider is configured (no API key in `.env`) or the provider is unreachable. Set an API key in `.env`, restart the API, and configure the provider via the admin API. Non-AI features continue working without a provider.

---

**Q: Which AI provider should I use?**

For a straightforward setup: **OpenAI**. It supports both chat and embeddings with a single key. For cost optimization: **Gemini** (also supports both). For access to many models: **OpenRouter** (chat only — you still need OpenAI or Gemini for embeddings).

---

**Q: What is the difference between `hybrid` and `rag_strict` profile retrieval modes?**

`hybrid` combines keyword and vector search — it returns results even when AI is unavailable (falls back to keyword only). `rag_strict` uses vector search only — higher quality when AI is healthy, but returns an error (or empty results) when unavailable. Use `rag_strict` for production with a reliable provider; use `hybrid` when you want resilience to AI downtime.

---

**Q: Can anonymous users search the marketplace?**

Only if `discovery.access.anonymous_search_enabled: true` in `marketplace.yaml`. Default is `false`. When enabled, `anonymous_filter_mode` controls which filters they can use (`public_only` is the safest default).

---

**Q: How does profile completeness work?**

Completeness is calculated as the percentage of `required: true` fields that are non-empty. The `profile_completeness_threshold` setting per participant type (0–100) controls the minimum percentage needed before a user can submit their profile.

---

**Q: What is a "managed zone"?**

Managed zones are directories that the compiler writes to: `app/generated/`, `alembic/versions/auto_marketplace_*.py`, `openapi/generated_openapi.json`, and `generated/manifest.json`. Never hand-edit files in these directories — they are overwritten on the next compile.

---

**Q: Can I run the wizard and the full API at the same time?**

It is not recommended. The setup service and main API share the same `marketplace.yaml`. If you modify and regenerate config while the API is running, you need to restart the API for changes to take effect. The typical workflow is: stop the API → run wizard → generate → start the API.

---

**Q: How do I change the admin password?**

Currently there is no dedicated password change endpoint. As a workaround: deactivate the old admin account and bootstrap a new one, or update the `password_hash` directly in the database using bcrypt.

---

**Q: What are conversation approval rules?**

When a conversation rule has `requires_approval: true`, the receiver must explicitly accept the request before messaging begins. The initiator sends a conversation request; the receiver sees it as pending and can accept or reject. This gives supply-side types control over which buyers they engage with.

---

**Q: How do I upload documents for the AI knowledge base?**

Use the admin API:

```bash
curl -X POST http://localhost:18000/api/ai/documents \
  -H "Content-Type: application/json" \
  -b "session_token=YOUR_ADMIN_TOKEN" \
  -d '{"filename": "guide.txt", "content": "..."}'
```

The document is chunked and indexed asynchronously. Check `GET /api/admin/ai/documents` for status.

---

**Q: Can I have multiple sections in a profile schema?**

Yes. Each participant type can have multiple sections, and each section has its own list of fields. Sections are display groupings — they don't affect API behavior.

---

**Q: What happens if I set `document_upload_required: true` but `ai_extraction_enabled: false`?**

Documents are uploaded but not processed by AI. The user must fill their profile fields manually. The uploaded documents are stored and can be viewed by admins.

---

**Q: How do I see the generated API for my participant types?**

Visit `http://localhost:18000/docs` after starting the API. You'll see generated role-specific routes like `/api/roles/producer/register`, `/api/roles/producer/me`, etc., alongside the generic `/api/profiles/{type_slug}/...` routes.

---

**Q: Can I use a custom domain in production?**

Yes. Point your domain's DNS to your server and configure `CORS_ORIGINS` in `.env` with your frontend URL. Update `docker-compose.yml` port mappings as needed, or use a reverse proxy (nginx, Caddy) in front of the API container.

---

## See Also
- [Quick Start](quick-start.md) — first-run instructions
- [Marketplace Config Reference](marketplace-config.md) — every config option explained
- [Admin Guide](admin-guide.md) — managing your running marketplace
- [Troubleshooting](troubleshooting.md) — fix common issues

---

[← Troubleshooting](troubleshooting.md)
