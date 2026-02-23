# Marketplace Config Reference

`marketplace.yaml` is the single source of truth for all runtime behavior. Every decision about participant types, profile schemas, onboarding, communication, and discovery lives in this file.

## Full Example

```yaml
marketplace:
  name: "GrainPlaza"
  description: "Connecting specialty grain producers with global buyers"
  industry: "Specialty Agriculture"

participant_types:
  - name: Producer
    slug: producer
    role: supply
    permissions:
      can_list: true
      can_search: false
      can_initiate_conversation: false
      can_receive_conversation: true
      can_share_private_assets: true
      requires_onboarding: true
      requires_approval: true
      visible_in_search: true

  - name: Buyer
    slug: buyer
    role: demand
    permissions:
      can_list: false
      can_search: true
      can_initiate_conversation: true
      can_receive_conversation: true
      can_share_private_assets: false
      requires_onboarding: true
      requires_approval: false
      visible_in_search: false

profile_schemas:
  producer:
    sections:
      - name: Basic Information
        fields:
          - name: farm_name
            label: Farm Name
            type: text
            required: true
            visibility: public
            searchable: true
          - name: country
            label: Country
            type: select
            required: true
            options: [Canada, USA, Brazil]
            visibility: public
            searchable: true
          - name: primary_crops
            label: Primary Crops
            type: multi_select
            required: true
            options: [Wheat, Corn, Soybeans, Barley]
            visibility: public
            searchable: true
  buyer:
    sections:
      - name: Organization
        fields:
          - name: org_name
            label: Organization Name
            type: text
            required: true
            visibility: public
            searchable: true

onboarding:
  producer:
    requires_approval: true
    approval_type: manual
    document_upload_required: true
    ai_extraction_enabled: true
    ai_profile_generation: true
    welcome_email_on_approval: true
    profile_completeness_threshold: 80
  buyer:
    requires_approval: false
    approval_type: auto
    document_upload_required: false
    ai_extraction_enabled: false
    ai_profile_generation: false
    welcome_email_on_approval: true
    profile_completeness_threshold: 100

communication:
  conversation_rules:
    - initiator: buyer
      receiver: producer
      requires_approval: true

discovery:
  searchable_types: [producer]
  filter_fields: [country, primary_crops]
  result_visibility:
    anonymous: public
    authenticated: protected
  access:
    anonymous_search_enabled: false
    anonymous_filter_mode: public_only
  ai:
    vector_search_enabled: true
    rag_query_enabled: true
    follow_up_suggestions: true
    profile_retrieval_mode: rag_strict
    rag_failure_behavior: service_unavailable
    profile_similarity_threshold: 0.25
    max_vector_candidates: 500
```

---

## `marketplace`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Marketplace display name. Used in admin panels, emails, and the health endpoint. |
| `description` | string | No | Short description of what your marketplace does. |
| `industry` | string | No | Industry vertical. Informational only. |

---

## `participant_types`

List of 2–3 participant type objects. At least one must have `can_search: true` and at least one must have `visible_in_search: true`.

### Type fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name (e.g. "Producer") |
| `slug` | string | Yes | URL-safe lowercase identifier (e.g. `producer`). Used in API paths. Breaking if changed after generation. |
| `role` | `supply` \| `demand` \| `facilitator` | Yes | Market side this type represents |
| `permissions` | object | Yes | Permission flags (see below) |

### Permissions

| Permission | Type | Description |
|------------|------|-------------|
| `can_list` | bool | Can create/maintain a profile that appears in discovery |
| `can_search` | bool | Can run discovery searches |
| `can_initiate_conversation` | bool | Can start a conversation with another user |
| `can_receive_conversation` | bool | Can be contacted by others |
| `can_share_private_assets` | bool | Can attach private files in conversations |
| `requires_onboarding` | bool | Must complete profile onboarding before accessing the platform |
| `requires_approval` | bool | Admin must approve the profile before it goes live |
| `visible_in_search` | bool | Profile appears in search results (also determines if discovery returns this type) |

> **Tip:** Supply-side types typically have `can_list: true`, `visible_in_search: true`, `requires_approval: true`. Demand-side types typically have `can_search: true`, `visible_in_search: false`, `requires_approval: false`.

---

## `profile_schemas`

One schema per participant type slug. Defines the profile structure for each type.

### Structure

```yaml
profile_schemas:
  <slug>:
    sections:
      - name: <section name>
        fields:
          - name: <field_key>
            label: <display label>
            type: <field type>
            required: true|false
            visibility: public|protected|private
            searchable: true|false
            options: [...]  # required for select/multi_select
```

### Field types

| Type | Storage | Notes |
|------|---------|-------|
| `text` | string | Free-text input |
| `number` | float | Numeric input |
| `select` | string | Single-choice dropdown; `options` required |
| `multi_select` | list[string] | Multi-choice; `options` required |
| `date` | string | Date string (ISO format) |
| `file` | string | File reference ID (uploaded via the files API) |
| `rich_text` | string | Formatted text (HTML) |
| `location` | dict | Location object with address/coordinates |

### Field properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | — | Unique field key within the schema. Used in API payloads. |
| `label` | string | — | Display label shown to users |
| `type` | string | — | Field type (see table above) |
| `required` | bool | `false` | Whether the field counts toward profile completeness |
| `options` | list | — | Choices for `select`/`multi_select` fields. Required if type is `select` or `multi_select`. |
| `visibility` | string | `public` | Who can see this field (see below) |
| `searchable` | bool | `false` | Whether this field is indexed for search |

### Visibility levels

| Level | Visible to | Typical use |
|-------|-----------|------------|
| `public` | Everyone, including unauthenticated users | Name, company, category |
| `protected` | Authenticated users only | Production capacity, pricing range |
| `private` | Profile owner and admins only | Internal notes, financial details |

---

## `onboarding`

One config per participant type slug. Controls what happens when a new user registers as that type.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `requires_approval` | bool | `true` | Admin must approve the profile before it goes live |
| `approval_type` | `manual` \| `auto` | `manual` | `manual` requires human action; `auto` approves immediately |
| `document_upload_required` | bool | `false` | User must upload at least one document during onboarding |
| `ai_extraction_enabled` | bool | `false` | AI reads uploaded documents and pre-fills profile fields. Requires `document_upload_required: true`. |
| `ai_profile_generation` | bool | `false` | AI generates a profile draft from uploaded content. Requires an AI provider to be configured. |
| `welcome_email_on_approval` | bool | `true` | Send a welcome email when the profile is approved. Requires `RESEND_API_KEY`. |
| `profile_completeness_threshold` | int (0–100) | `100` | Minimum completeness percentage required before the user can submit the profile |

**Constraints:**
- `requires_approval: false` forces `approval_type: auto`
- `document_upload_required: false` forces `ai_extraction_enabled: false`

---

## `communication`

Defines which participant types can contact which others.

### `conversation_rules`

List of rules. Each rule:

| Field | Type | Description |
|-------|------|-------------|
| `initiator` | string | Slug of the type that starts the conversation |
| `receiver` | string | Slug of the type that receives the conversation request |
| `requires_approval` | bool | Whether the receiver must explicitly accept before messaging begins |

Both `initiator` and `receiver` must be valid participant type slugs. If no rules are defined, users cannot contact each other.

---

## `discovery`

Controls search behavior, result visibility, and AI discovery features.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `searchable_types` | list[string] | `[]` | Type slugs that appear in search results. Must include only types with `visible_in_search: true`. |
| `filter_fields` | list[string] | `[]` | Profile field keys available as search filters. Must exist in at least one profile schema. |

### `result_visibility`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `anonymous` | `public` | `public` | Fields shown to unauthenticated search users |
| `authenticated` | `public` \| `protected` | `protected` | Fields shown to authenticated search users |

### `access`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `anonymous_search_enabled` | bool | `false` | Allow unauthenticated users to use `/api/search`. Default `false` recommended. |
| `anonymous_filter_mode` | `public_only` \| `none` \| `all` | `public_only` | Which filters anonymous users can apply. `public_only` restricts to filters on public fields. |

### `ai`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vector_search_enabled` | bool | `true` | Enable semantic/vector search alongside keyword search |
| `rag_query_enabled` | bool | `true` | Enable RAG-assisted answers to natural language queries |
| `follow_up_suggestions` | bool | `true` | AI suggests follow-up queries after a search |
| `profile_retrieval_mode` | `hybrid` \| `rag_strict` | `hybrid` | `hybrid` uses both keyword and vector; `rag_strict` uses vector only (falls back on failure per `rag_failure_behavior`) |
| `rag_failure_behavior` | `service_unavailable` \| `empty` | `service_unavailable` | What happens when vector retrieval is unavailable in `rag_strict` mode: return 503 or return empty results |
| `profile_similarity_threshold` | float (0–1) | `0.25` | Minimum cosine similarity score for a profile to be returned in vector search |
| `max_vector_candidates` | int (≥1) | `500` | Maximum number of vector candidates to retrieve before keyword re-ranking |

**Constraint:** `rag_strict` mode requires `vector_search_enabled: true`.

> **Recommendation:** Use `profile_retrieval_mode: rag_strict` for better semantic accuracy. Use `hybrid` if you need results even when the AI service is down.

---

## Cross-Validation Rules

The config is validated at load time and on every wizard save. Violations block generation.

1. 2–3 participant types required (MVP limit)
2. Profile schema must exist for every participant type slug
3. Onboarding config must exist for every participant type slug
4. Conversation rules must reference valid participant type slugs
5. At least one type must have `can_search: true`
6. At least one type must have `visible_in_search: true`
7. `searchable_types` must reference valid participant type slugs
8. `searchable_types` may only include types with `visible_in_search: true`
9. `filter_fields` must match field keys in at least one profile schema
10. `select`/`multi_select` fields must have a non-empty `options` list
11. `profile_similarity_threshold` must be between 0 and 1
12. `max_vector_candidates` must be ≥ 1
13. `rag_strict` mode requires `vector_search_enabled: true`

---

## CLI Validation

```bash
# Validate config structure
python -m cli validate marketplace.yaml

# Check that generated artifacts match current config
python -m cli compile --check --config marketplace.yaml --mode mvp
```

`validate` checks the schema and prints participant types on success. `compile --check` verifies that compiled artifacts are in sync with the config — use this as a CI gate.

---

## See Also
- [Setup Wizard](setup-wizard.md) — configure everything in the browser
- [Environment Variables](environment.md) — runtime secrets and settings
- [AI Features](ai-features.md) — provider setup for AI discovery

---

[← Setup Wizard](setup-wizard.md) · [Environment Variables →](environment.md)
