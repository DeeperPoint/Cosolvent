# AI Features

Cosolvent provides AI-powered profile generation, semantic search, and RAG-based Q&A. This page covers what each feature does, how to enable it, and which provider to use.

## What AI Features Exist

| Feature | What it does | Requires |
|---------|-------------|---------|
| **Semantic search** | Finds profiles by meaning, not just keyword matching | Any provider with embeddings |
| **RAG Q&A** | Answers natural language queries using your knowledge base documents | Any provider with embeddings + chat |
| **Follow-up suggestions** | Suggests related queries after a search or Q&A response | Chat model |
| **AI profile generation** | Generates a draft profile from documents uploaded during onboarding | Chat model |
| **AI document extraction** | Reads uploaded onboarding documents and pre-fills profile fields | Chat model |
| **AI-assisted registration** | On the public registration form, applicants can describe their business in text or by voice; an LLM pre-fills the form fields for them to review and edit | Chat model (voice: browser Web Speech API, no key) |

AI features degrade gracefully: if no provider is configured, all AI endpoints return `503 Service Unavailable`. All other marketplace flows (auth, profiles, conversations) continue normally.

---

## Supported Providers

| Provider | Chat | Embeddings | Key Variable |
|----------|------|------------|-------------|
| **OpenAI** | Yes | Yes | `OPENAI_API_KEY` |
| **OpenRouter** | Yes | No | `OPENROUTER_API_KEY` |
| **Google Gemini** | Yes | Yes | `GEMINI_API_KEY` |

**Cohere** (`COHERE_API_KEY`) is optional and used for search result reranking when present.

---

## Setting Up a Provider

### 1. Add the API key to `.env`

```env
# Pick one (or more):
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AI...
```

### 2. Configure the active provider via the Admin API

```bash
curl -X PUT http://localhost:18000/api/admin/ai/settings \
  -H "Content-Type: application/json" \
  -b "session_token=YOUR_ADMIN_TOKEN" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.5,
    "max_tokens": 2048
  }'
```

Changes take effect immediately — no restart required.

**Recommended defaults by provider:**

| Provider | Recommended model | Notes |
|----------|-----------------|-------|
| OpenAI | `gpt-4o` | Best quality; supports embeddings |
| OpenRouter | `anthropic/claude-3.5-sonnet` | Good quality; no embeddings (use OpenAI for embeddings) |
| Gemini | `gemini-1.5-pro` | Cost-effective; supports embeddings |

### 3. Verify

```bash
curl http://localhost:18000/api/admin/ai/models \
  -b "session_token=YOUR_ADMIN_TOKEN"
```

Returns available models for the active provider.

---

## Embedding Configuration

Embeddings are used for semantic search and RAG. Only providers with `supports_embeddings: true` (OpenAI, Gemini) can serve as embedding providers.

If you use OpenRouter for chat, you must also configure an OpenAI or Gemini key for embeddings. The system uses the configured embedding provider separately from the chat provider.

Default embedding models:
- OpenAI: `text-embedding-3-small` (1536 dimensions)
- Gemini: `text-embedding-004` (768 dimensions)

---

## Enabling AI Features in marketplace.yaml

AI discovery features are controlled in `marketplace.yaml` under `discovery.ai`:

```yaml
discovery:
  ai:
    vector_search_enabled: true        # Enable semantic search
    rag_query_enabled: true            # Enable RAG Q&A endpoint
    follow_up_suggestions: true        # Enable follow-up query suggestions
    profile_retrieval_mode: rag_strict # Use vector-only retrieval (or "hybrid")
    rag_failure_behavior: service_unavailable
    profile_similarity_threshold: 0.25
    max_vector_candidates: 500
```

AI onboarding features are controlled per participant type under `onboarding`:

```yaml
onboarding:
  producer:
    document_upload_required: true
    ai_extraction_enabled: true    # Extract profile fields from uploaded docs
    ai_profile_generation: true    # Generate profile draft from uploaded docs
```

---

## Uploading RAG Documents

RAG documents are indexed as text chunks and used to answer user queries. Upload them via the admin API:

```bash
curl -X POST http://localhost:18000/api/ai/documents \
  -H "Content-Type: application/json" \
  -b "session_token=YOUR_ADMIN_TOKEN" \
  -d '{
    "filename": "marketplace-faq.txt",
    "content": "Q: How do I register?\nA: Visit the signup page..."
  }'
```

The document is processed asynchronously:
1. Text is split into chunks
2. Each chunk is embedded and stored in `ai_document_chunks`
3. Document status updates from `processing` → `indexed`

Check processing status:

```bash
curl http://localhost:18000/api/admin/ai/documents \
  -b "session_token=YOUR_ADMIN_TOKEN"
```

---

## AI-Powered Profile Generation

When `ai_profile_generation: true` is set for a participant type, users can trigger AI generation from their profile page:

```
POST /api/profiles/{type_slug}/{profile_id}/ai-generate
```

This generates a draft profile based on any documents the user uploaded during onboarding. An admin can then approve or reject the AI draft:

```
POST /api/profiles/{type_slug}/{profile_id}/ai-approve
POST /api/profiles/{type_slug}/{profile_id}/ai-reject
```

---

## AI-Assisted Registration

The public registration form (`/register/{type}`) offers three ways to fill it in — **Fill in the form**, **Describe in text**, and **Use voice** — whenever `ai_extraction_enabled: true` is set for that participant type.

- **Describe in text** — the applicant writes or pastes a short description of their business. The backend extracts the structured form fields and pre-fills them.
- **Use voice** — the applicant dictates the description. Transcription happens in the browser via the Web Speech API (no API key, no server round-trip; works in Chrome, Edge, and Safari — Firefox falls back to the text box). The transcript then goes through the same extraction.

Both paths are **assistive only**: nothing is submitted automatically. The form is pre-filled, low-confidence guesses are flagged for confirmation, and the applicant reviews and edits everything before submitting the application as normal.

```
POST /api/profiles/{type_slug}/register/extract
Body: { "text": "We're a Hamilton machine shop running two 5-axis centres..." }
```

This endpoint is anonymous (no account exists yet), stateless (nothing is saved), and per-IP rate-limited. Field extraction defaults to `openrouter` / `google/gemini-2.5-flash` — a low-cost model that reliably honours the JSON-schema response format extraction depends on. Override it per use case (`document_extraction`) through the LLM settings API if you prefer another model.

---

## Vector Search Configuration

**`profile_retrieval_mode: hybrid`** — combines keyword search with vector similarity. Returns results even if the vector service is unavailable (falls back to keyword only).

**`profile_retrieval_mode: rag_strict`** — uses vector search only. If the vector service is unavailable, returns an error (or empty results, depending on `rag_failure_behavior`). Higher quality when AI is healthy.

**`profile_similarity_threshold`** — profiles below this cosine similarity score are excluded from results. Increase (e.g. to 0.4) for stricter matching; decrease (e.g. to 0.1) to return more results.

**`max_vector_candidates`** — controls the size of the initial vector retrieval set before keyword re-ranking. Higher values increase recall at the cost of latency.

---

## Prompt Template Customization

Customize the system prompts for AI features:

```bash
# List available intents
curl http://localhost:18000/api/admin/ai/prompts \
  -b "session_token=YOUR_ADMIN_TOKEN"

# Update a prompt
curl -X PUT http://localhost:18000/api/admin/ai/prompts/rag_query \
  -H "Content-Type: application/json" \
  -b "session_token=YOUR_ADMIN_TOKEN" \
  -d '{"template": "You are a helpful assistant for {marketplace_name}. Answer based on the provided context..."}'
```

---

## See Also
- [Admin Guide](admin-guide.md) — managing AI settings via API
- [Marketplace Config Reference](marketplace-config.md) — discovery.ai options
- [Troubleshooting](troubleshooting.md) — AI 503 errors and indexing failures

---

[← Admin Guide](admin-guide.md) · [Troubleshooting →](troubleshooting.md)
