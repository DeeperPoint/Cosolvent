# AI Architecture

How the multi-provider AI system works: provider registry, client factories, LLM client, embedding client, RAG pipeline, and profile generation flow.

## Multi-Provider Pattern

All AI providers are accessed via the `openai` SDK with a configurable `base_url`. This means the same client interface works for OpenAI, OpenRouter, and Gemini — only the base URL and API key change.

```python
from openai import AsyncOpenAI

# OpenAI (native)
client = AsyncOpenAI(api_key="sk-...")

# OpenRouter
client = AsyncOpenAI(
    api_key="sk-or-...",
    base_url="https://openrouter.ai/api/v1"
)

# Gemini
client = AsyncOpenAI(
    api_key="AI...",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
```

## Provider Registry (`app/modules/ai/providers.py`)

The `PROVIDER_REGISTRY` maps provider IDs to `ProviderSpec` objects:

```python
class ProviderSpec:
    id: ProviderID
    name: str
    base_url: str | None            # None = use default OpenAI URL
    supports_embeddings: bool
    default_embedding_model: str | None
    default_embedding_dimensions: int | None
    api_key_env_name: str           # name of the settings field
```

| Provider | ID | Embeddings | Default embedding model | Dimensions |
|----------|-----|------------|------------------------|-----------|
| OpenAI | `openai` | Yes | `text-embedding-3-small` | 1536 |
| OpenRouter | `openrouter` | No | — | — |
| Gemini | `gemini` | Yes | `text-embedding-004` | 768 |

## Client Factory (`app/modules/ai/client_factory.py`)

Two factory functions create configured `AsyncOpenAI` instances:

### `get_chat_client(provider_id) -> AsyncOpenAI`

Returns a client configured for chat completions. Reads the API key from `settings` using `provider_spec.api_key_env_name`. Raises `ServiceUnavailableError` if the key is not set.

### `get_embedding_client(provider_id) -> AsyncOpenAI`

Same pattern, but only for providers with `supports_embeddings: True`. Raises `ServiceUnavailableError` for OpenRouter (which has no embedding support).

## LLM Client (`app/modules/ai/llm_client.py`)

The LLM client is the high-level interface used by services. It:
1. Loads the active provider/model/temperature/max_tokens from `ai_llm_settings` in MongoDB
2. Uses `get_chat_client(provider)` to get the SDK client
3. Dispatches to the appropriate use case (RAG query, profile generation, extraction, follow-up)

The settings are stored in MongoDB so they can be updated at runtime via the admin API without a restart.

## Embedding Client (`app/modules/ai/embedding_client.py`)

The embedding abstraction:

```python
async def get_embedding(text: str) -> list[float]:
    config = await repo.get_embedding_config()  # reads from ai_llm_settings
    client = get_embedding_client(config["provider"])
    resp = await client.embeddings.create(input=text, model=config["model"])
    return resp.data[0].embedding

async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    ...
```

The embedding config can differ from the chat config — useful when using OpenRouter for chat but OpenAI for embeddings.

## Prompt Manager (`app/modules/ai/prompt_manager.py`)

Prompt templates are stored in the `ai_prompts` MongoDB collection, keyed by `intent`. The prompt manager resolves a template by intent and interpolates variables (e.g. `{marketplace_name}`).

Admins can update templates via `PUT /api/admin/ai/prompts/{intent}`. Changes take effect on the next API call — no restart required.

## RAG Pipeline

End-to-end flow for a user query:

```
User query
    │
    ▼
1. Generate query embedding
   (get_embedding_client → embeddings.create)
    │
    ▼
2. Vector search: find top-k document chunks
   (ai_document_chunks table, IVFFlat ANN, threshold filter)
    │
    ▼
3. Rerank (optional, if COHERE_API_KEY set)
   (Cohere rerank API)
    │
    ▼
4. Build context string from top chunks
    │
    ▼
5. Load prompt template (intent = "rag_query")
    │
    ▼
6. Call chat model with context + user query
   (get_chat_client → chat.completions.create)
    │
    ▼
7. Save to ai_chat_messages, update thread
    │
    ▼
8. (Optional) Generate follow-up suggestions
   (separate chat call with intent = "follow_up")
    │
    ▼
Response to user
```

## Profile Discovery (Vector Search)

Profile search uses a separate flow from RAG:

```
Search query
    │
    ▼
1. Generate query embedding
    │
    ▼
2. ANN search on profile_vectors
   (filter by participant_type, status=active)
   (threshold: profile_similarity_threshold)
    │
    ▼
3. Keyword re-ranking (in hybrid mode)
    │
    ▼
4. Apply visibility filter to result fields
    │
    ▼
Results
```

In `rag_strict` mode, step 3 is skipped. If the embedding service is unavailable, the behavior is controlled by `rag_failure_behavior` (`service_unavailable` returns 503, `empty` returns no results).

## Profile Generation Flow

When `ai_profile_generation: true` is set for a participant type:

```
User uploads document(s) during onboarding
    │
    ▼
POST /api/profiles/{type_slug}/{profile_id}/ai-generate
    │
    ▼
1. Retrieve uploaded documents from S3
2. Extract text content
3. Build prompt: "generate a profile for a {type_name}..."
4. Call chat model
5. Parse structured response into profile field values
6. Store as profile.ai_profile (pending admin review)
    │
    ▼
Admin reviews via:
POST /api/profiles/{type_slug}/{profile_id}/ai-approve  → merge into profile.fields
POST /api/profiles/{type_slug}/{profile_id}/ai-reject   → discard ai_profile
```

## Document Chunking and Indexing

```
POST /api/ai/documents
    │
    ▼
1. Store document metadata in ai_documents (status: processing)
2. Enqueue process_document_task to ARQ
    │
    ▼ (async in worker)
3. Retrieve document content
4. Split into chunks (configurable size/overlap)
5. Batch embed all chunks (get_embeddings_batch)
6. Upsert into ai_document_chunks (with IVFFlat index update)
7. Update ai_documents.status → indexed (or failed)
```

## Error Handling

All AI operations wrap provider calls in try/except and raise `ServiceUnavailableError` on failure. This propagates as a `503` HTTP response. Non-AI flows are completely unaffected.

## See Also
- [Modules — AI](modules.md#ai-appmodulesai) — module-level overview
- [Workers](workers.md) — document and profile indexing jobs
- [Data Models](data-models.md) — ai_document_chunks, profile_vectors, ai_llm_settings
- [AI Features](../user/ai-features.md) — operator guide for setting up providers

---

[← Data Models](data-models.md) · [Background Workers →](workers.md)
