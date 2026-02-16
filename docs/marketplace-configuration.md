# Marketplace Configuration

The `marketplace.yaml` file is the single source of truth for all runtime behavior. It defines the marketplace identity, participant types, profile schemas, onboarding workflows, communication rules, and discovery settings.

## Configuration Structure

```yaml
marketplace:
  name: "GrainPlaza"
  description: "Connecting specialty grain producers with global buyers"
  industry: "Specialty Agriculture"

participant_types:
  - name: Producer
    slug: producer
    role: supply           # supply | demand | facilitator
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
            type: text           # text|number|select|multi_select|date|file|rich_text|location
            required: true
            visibility: public   # public|protected|private
            searchable: true
          - name: country
            label: Country
            type: select
            required: true
            options: [Canada, USA, Brazil]
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
    approval_type: manual          # manual | auto
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
    anonymous_filter_mode: public_only   # public_only | none | all
  ai:
    vector_search_enabled: true
    rag_query_enabled: true
    follow_up_suggestions: true
    profile_retrieval_mode: rag_strict   # hybrid | rag_strict
    rag_failure_behavior: service_unavailable  # service_unavailable | empty
    profile_similarity_threshold: 0.25
    max_vector_candidates: 500
```

## Sections

### `marketplace`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Marketplace display name |
| `description` | string | No | Short description |
| `industry` | string | No | Industry vertical |

### `participant_types`

2–3 participant types are required. Each type has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name |
| `slug` | string | URL-safe identifier |
| `role` | `supply` / `demand` / `facilitator` | Market role |
| `permissions` | object | Permission flags (see below) |

#### Permissions

| Permission | Description |
|------------|-------------|
| `can_list` | Can this type be listed/browsed |
| `can_search` | Can this type search for others |
| `can_initiate_conversation` | Can start conversations |
| `can_receive_conversation` | Can receive conversation requests |
| `can_share_private_assets` | Can share private files in conversations |
| `requires_onboarding` | Must complete onboarding flow |
| `requires_approval` | Needs admin approval to activate |
| `visible_in_search` | Appears in search results |

### `profile_schemas`

One schema per participant type slug. Each schema has sections, each section has fields.

#### Field Types

| Type | Python Type | Notes |
|------|-------------|-------|
| `text` | `str` | Free-text input |
| `number` | `float` | Numeric input |
| `select` | `str` | Single-choice; `options` required |
| `multi_select` | `list[str]` | Multi-choice; `options` required |
| `date` | `str` | Date string |
| `file` | `str` | File reference ID |
| `rich_text` | `str` | Formatted text |
| `location` | `dict` | Location object |

#### Field Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | — | Unique field identifier |
| `label` | string | — | Display label |
| `type` | string | — | One of the types above |
| `required` | bool | `false` | Required for profile completeness |
| `options` | list | — | Choices for select/multi_select |
| `visibility` | string | `public` | `public`, `protected`, or `private` |
| `searchable` | bool | `false` | Included in search index |

#### Visibility Levels

| Level | Who can see | Use case |
|-------|-------------|----------|
| `public` | Everyone (including anonymous) | Farm name, company name |
| `protected` | Authenticated users only | Production capacity, pricing |
| `private` | Profile owner + admins only | Financial notes, internal data |

### `onboarding`

One config per participant type slug.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `requires_approval` | bool | `true` | Admin must approve profile |
| `approval_type` | `manual` / `auto` | `manual` | Approval mechanism |
| `document_upload_required` | bool | `false` | Must upload documents during onboarding |
| `ai_extraction_enabled` | bool | `false` | AI extracts fields from documents |
| `ai_profile_generation` | bool | `false` | AI generates profile content |
| `welcome_email_on_approval` | bool | `true` | Send email when approved |
| `profile_completeness_threshold` | int | `100` | Minimum completeness % to submit |

### `communication`

| Field | Type | Description |
|-------|------|-------------|
| `conversation_rules` | list | Who can message whom |

Each rule:

| Field | Type | Description |
|-------|------|-------------|
| `initiator` | string | Type slug that starts the conversation |
| `receiver` | string | Type slug that receives the request |
| `requires_approval` | bool | Whether the receiver must accept first |

### `discovery`

| Field | Type | Description |
|-------|------|-------------|
| `searchable_types` | list[string] | Type slugs that appear in search |
| `filter_fields` | list[string] | Field names available as search filters |
| `result_visibility.anonymous` | `public` | Fields shown to anonymous users |
| `result_visibility.authenticated` | `public` / `protected` | Fields shown to logged-in users |
| `access.anonymous_search_enabled` | bool | Allow unauthenticated use of `/api/search` |
| `access.anonymous_filter_mode` | `public_only` / `none` / `all` | Anonymous filter policy |
| `ai.vector_search_enabled` | bool | Enable semantic/vector search |
| `ai.rag_query_enabled` | bool | Enable RAG Q&A |
| `ai.follow_up_suggestions` | bool | Enable AI follow-up suggestions |
| `ai.profile_retrieval_mode` | `hybrid` / `rag_strict` | Profile search retrieval strategy |
| `ai.rag_failure_behavior` | `service_unavailable` / `empty` | Strict-mode behavior when vector retrieval is unavailable |
| `ai.profile_similarity_threshold` | float (0..1) | Minimum vector similarity score in strict mode |
| `ai.max_vector_candidates` | int (`>= 1`) | Max vector candidates used during ranking |

## Cross-Validation Rules

The config is validated at load time. The following constraints are enforced:

1. **2–3 participant types** required (MVP limit)
2. **Profile schema** must exist for every participant type
3. **Onboarding config** must exist for every participant type
4. **Conversation rules** must reference valid type slugs
5. At least one type must have **`can_search: true`**
6. At least one type must have **`visible_in_search: true`**
7. **`searchable_types`** must reference valid type slugs
8. **`searchable_types`** must only include types with **`visible_in_search: true`**
9. **`filter_fields`** must exist in at least one profile schema
10. `select`/`multi_select` fields must have **`options`** defined
11. `ai.profile_similarity_threshold` must be within **0..1**
12. `ai.max_vector_candidates` must be **>= 1**

## CLI Validation

Validate a config file without starting the server:

```bash
python -m cli validate marketplace.yaml
```

On success, prints the marketplace name and participant types. On failure, prints per-field validation errors with their location.
