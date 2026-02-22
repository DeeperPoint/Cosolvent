# Setup Technical Reference

This document covers the setup module internals: the API surface, config schema, compilation pipeline, CLI commands, and frontend architecture. Read this if you are extending, debugging, or integrating with the setup system.

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser                                                         │
│  panel_v2.html → main.js (state) → API calls                    │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTP
┌──────────────▼───────────────────────────────────────────────────┐
│  Setup Service (FastAPI)            app/modules/setup/router.py  │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │ validate │ │ save     │ │ render-yaml│ │ generate / check │  │
│  └────┬─────┘ └────┬─────┘ └─────┬──────┘ └────────┬─────────┘  │
│       │             │             │                  │            │
│  ┌────▼─────────────▼─────────────▼──────────────────▼────────┐  │
│  │  MarketplaceConfig (Pydantic)   app/core/marketplace_config │  │
│  └────────────────────────────────────────────┬───────────────┘  │
│                                               │                  │
│  ┌────────────────────────────────────────────▼───────────────┐  │
│  │  Compiler pipeline              app/compiler/              │  │
│  │  normalize → IR → render → write                           │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│  Generated artifacts                                             │
│  app/generated/    alembic/versions/    openapi/    exports/     │
└──────────────────────────────────────────────────────────────────┘
```

---

## API endpoints

All endpoints are registered on the setup router, mounted at `/`.

### `GET /onboarding`

Returns `panel_v2.html` as an HTML response. This is the full onboarding wizard SPA.

### `GET /api/setup/assets/{asset_name}`

Serves static frontend assets. Whitelisted filenames only (prevents path traversal):

```
main.js  tokens.js  help-content.js  steps.js
validation-mapper.js  diff-renderer.js  state-utils.js
onboarding-v2.css
```

### `GET /api/setup/config-template`

Loads the current configuration. Tries runtime config first, falls back to `marketplace.example.yaml`.

```json
// Response
{
  "config": { },
  "source_path": "marketplace.yaml",
  "runtime_path": "/app/marketplace.yaml",
  "seeded_from_example": false
}
```

### `GET /api/setup/presets`

Returns the built-in preset list (`app/modules/setup/presets.py`). Three presets ship by default: `agriculture_b2b`, `services_b2b`, `manufacturing_b2b`. Each preset contains a complete `MarketplaceConfig` dict.

```json
// Response
{
  "presets": [
    {
      "id": "agriculture_b2b",
      "title": "Agriculture Marketplace",
      "description": "...",
      "when_to_use": "...",
      "config": { }
    }
  ]
}
```

### `POST /api/setup/validate`

Validates a config dict against `MarketplaceConfig`. Returns the normalized config on success, or structured errors on failure.

```json
// Request
{ "config": { } }

// Success (200)
{ "valid": true, "config": { } }

// Failure (400)
{
  "detail": {
    "message": "Config validation failed",
    "errors": [
      { "loc": ["config", "participant_types"], "msg": "...", "type": "..." }
    ]
  }
}
```

### `POST /api/setup/render-yaml`

Renders config as YAML text.

```json
// Request
{ "config": { } }

// Response
{ "yaml": "marketplace:\n  name: ..." }
```

### `POST /api/setup/save`

Validates, then writes config to disk. Optionally loads it into runtime.

```json
// Request
{
  "config": { },
  "output_path": "marketplace.yaml",
  "apply_runtime": true
}

// Response
{
  "saved": true,
  "path": "marketplace.yaml",
  "bytes": 2048,
  "applied_runtime": true
}
```

Path validation: must end in `.yaml`/`.yml`, must be within the project directory.

### `POST /api/setup/generate`

Runs the full compiler pipeline. Optionally creates an export archive.

```json
// Request
{
  "config": null,
  "mode": "mvp",
  "export_enabled": true,
  "export_dir": "exports",
  "overwrite_policy": "managed"
}

// Response
{
  "spec_hash": "sha256:abc...",
  "migration_revision": "cd0965b20114",
  "generated_files": ["app/generated/marketplace_spec.py", "..."],
  "removed_files": [],
  "export_path": "exports/marketplace-abc123.tar.gz",
  "warnings": []
}
```

If `config` is null, uses the current runtime config.

### `POST /api/setup/generate/check`

Dry-run sync check. Does not write files.

```json
// Request
{ "config": null, "mode": "mvp", "overwrite_policy": "managed" }

// Response
{
  "in_sync": true,
  "expected_spec_hash": "sha256:abc...",
  "current_manifest_hash": "sha256:abc...",
  "drift_files": []
}
```

---

## Configuration schema

The `MarketplaceConfig` Pydantic model lives at `app/core/marketplace_config.py`. Below is the full key reference.

### `marketplace`

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | string | yes | Marketplace brand name |
| `description` | string | no | Short purpose statement |
| `industry` | string | no | Industry vertical |

### `participant_types` (array, 2–3 items)

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Display name |
| `slug` | string | URL-safe identifier. **Breaking** if renamed after generation |
| `role` | `supply` \| `demand` \| `facilitator` | Market side |
| `permissions.can_list` | bool | Can publish listings |
| `permissions.can_search` | bool | Can run searches |
| `permissions.can_initiate_conversation` | bool | Can start conversations |
| `permissions.can_receive_conversation` | bool | Can receive messages |
| `permissions.can_share_private_assets` | bool | Can share files |
| `permissions.requires_onboarding` | bool | Must finish onboarding |
| `permissions.requires_approval` | bool | Needs admin approval |
| `permissions.visible_in_search` | bool | Appears in search results |

Cross-validation: at least one type must have `can_search: true` and one must have `visible_in_search: true`.

### `profile_schemas` (object, keyed by slug)

```yaml
profile_schemas:
  producer:
    sections:
      - name: "Basic Information"
        fields:
          - name: farm_name
            label: "Farm Name"
            type: text
            required: true
            options: null
            visibility: public
            searchable: true
```

Field types: `text`, `number`, `select`, `multi_select`, `date`, `file`, `rich_text`, `location`.

Visibility levels: `public` (everyone), `protected` (authenticated), `private` (owner + admins).

`select` and `multi_select` types require a non-empty `options` array.

### `onboarding` (object, keyed by slug)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `requires_approval` | bool | `true` | Admin must approve profile |
| `approval_type` | `manual` \| `auto` | `manual` | How approval happens |
| `document_upload_required` | bool | `false` | Must upload docs during onboarding |
| `ai_extraction_enabled` | bool | `false` | AI reads uploaded docs to fill fields |
| `ai_profile_generation` | bool | `false` | AI generates profile draft |
| `welcome_email_on_approval` | bool | `true` | Send email on approval |
| `profile_completeness_threshold` | int (0–100) | `100` | Min completeness to submit |

Constraints: `requires_approval: false` forces `approval_type: auto`. `document_upload_required: false` forces `ai_extraction_enabled: false`.

### `communication`

```yaml
communication:
  conversation_rules:
    - initiator: buyer
      receiver: producer
      requires_approval: true
```

Both `initiator` and `receiver` must be valid participant slugs. At least one rule recommended.

### `discovery`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `searchable_types` | string[] | `[]` | Slugs searchable in discovery |
| `filter_fields` | string[] | `[]` | Profile fields usable as filters |
| `result_visibility.anonymous` | `public` | `public` | What anonymous users see |
| `result_visibility.authenticated` | `public` \| `protected` | `protected` | What signed-in users see |
| `access.anonymous_search_enabled` | bool | `false` | Allow unauthenticated search |
| `access.anonymous_filter_mode` | `public_only` \| `none` \| `all` | `public_only` | Which filters anonymous users can use |
| `ai.vector_search_enabled` | bool | `true` | Semantic search |
| `ai.rag_query_enabled` | bool | `true` | RAG-assisted answers |
| `ai.follow_up_suggestions` | bool | `true` | AI suggests follow-up queries |
| `ai.profile_retrieval_mode` | `hybrid` \| `rag_strict` | `hybrid` | Search strategy |
| `ai.rag_failure_behavior` | `service_unavailable` \| `empty` | `service_unavailable` | What happens when RAG fails |
| `ai.profile_similarity_threshold` | float (0–1) | `0.25` | Min vector similarity |
| `ai.max_vector_candidates` | int (≥1) | `500` | Max vectors to rank |

Cross-validation: `rag_strict` mode requires `vector_search_enabled: true`.

---

## Compiler pipeline

The compiler transforms a `MarketplaceConfig` into deployable artifacts. Located in `app/compiler/`.

### Stages

```
Config dict
  │
  ▼
┌─────────────────────┐
│ 1. Normalize         │  compiler/normalize.py
│    Parse + validate  │  → MarketplaceConfig
│    Fill defaults     │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2. IR generation     │  compiler/ir.py
│    Config → pure     │  → Intermediate Representation
│    data structures   │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 3. Render            │  compiler/render.py
│    IR → file text    │  → Dict[filepath, content]
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4. Write             │  compiler/writer.py
│    Emit to disk      │  → Files + manifest
│    Managed zones     │
└─────────────────────┘
```

### Generated artifacts

| File | Purpose |
|------|---------|
| `app/generated/marketplace_spec.py` | Parsed config as a Python dataclass |
| `app/generated/role_registry.py` | Role definitions, slug-to-name mappings |
| `app/generated/role_alias_router.py` | Role-based route aliases (`/api/producers/...`) |
| `app/generated/profile_models.py` | Dynamic Pydantic models for profile validation |
| `app/generated/policy_matrix.py` | Permission and visibility decision matrices |
| `app/generated/enums.py` | Enums derived from config values |
| `alembic/versions/auto_marketplace_*.py` | Database migration |
| `openapi/generated_openapi.json` | OpenAPI 3.1 specification |
| `generated/manifest.json` | Build metadata, spec hash, file list |

### Determinism

The pipeline is deterministic: identical input config always produces identical output. The `spec_hash` is a SHA-256 of the normalized, JSON-serialized config. The `compile-check` command verifies this invariant and is suitable as a CI gate.

### Managed zones

The writer only touches files in managed directories. It will never modify user code:

- `app/generated/*`
- `alembic/versions/auto_marketplace_*.py`
- `openapi/generated_openapi.json`
- `generated/manifest.json`
- `exports/*.tar.gz`

### Export format

When export is enabled, the writer creates a timestamped tarball:

```
exports/marketplace-<short-hash>.tar.gz
```

Contains all generated files plus the manifest. Ready for deployment handoff.

---

## CLI commands

Entry point: `python -m cli` (or `cli/__main__.py`).

### `wizard`

Interactive 7-step config builder. Writes to disk on completion.

```bash
python -m cli wizard                          # default: marketplace.yaml
python -m cli wizard -o my-config.yaml        # custom output
python -m cli wizard --preset agriculture     # start from preset
python -m cli wizard --preset professional_services
```

### `validate`

Validate an existing YAML config against the Pydantic schema.

```bash
python -m cli validate                        # default: marketplace.yaml
python -m cli validate path/to/config.yaml
```

Exit code 0 on success, 1 on failure. Prints participant types and marketplace name on success.

### `compile`

Run the compiler pipeline.

```bash
python -m cli compile                                  # defaults
python -m cli compile --config my-config.yaml          # custom config
python -m cli compile --mode strict                    # strict mode
python -m cli compile --check                          # dry-run sync check
python -m cli compile --export                         # also create tarball
python -m cli compile --export --export-dir dist       # custom export dir
```

### `export`

Shorthand for `compile --export`.

```bash
python -m cli export
python -m cli export --export-dir dist
```

---

## Makefile targets

| Target | Command | Description |
|--------|---------|-------------|
| `make wizard` | `python -m cli wizard` | Interactive wizard |
| `make validate-config` | `python -m cli validate marketplace.example.yaml` | Validate example config |
| `make compile` | `python -m cli compile --config marketplace.yaml --mode mvp` | Generate artifacts |
| `make compile-check` | `python -m cli compile --check ...` | CI sync gate |
| `make export` | `python -m cli export ...` | Generate + export tarball |
| `make setup-up` | `docker compose up -d --build setup` | Start setup service only |
| `make setup-down` | `docker compose stop setup` | Stop setup service |
| `make onboarding` | (prints URLs) | Show wizard URLs |
| `make smoke-setup` | curl tests | Smoke test setup endpoints |

---

## Frontend architecture

The wizard is a single-page application served from `panel_v2.html`, built with vanilla JS modules.

### Module map

```
panel_v2.html
  └─ main.js              State management, rendering, event handling
       ├─ tokens.js        Design tokens (colors, fonts, motion timing)
       ├─ steps.js         Step definitions (titles, hints) — 7 steps
       ├─ help-content.js  100+ field-level help entries + glossary terms
       ├─ validation-mapper.js  Maps Pydantic errors to UI messages + step routing
       ├─ diff-renderer.js     Config diff computation + HTML rendering
       └─ state-utils.js       Config manipulation, slug remapping, normalization
```

### State model

Global mutable state in `main.js`:

```js
configState        // MarketplaceConfig dict — the source of truth
activeStep         // 0–6 (current wizard step)
previousStep       // for directional animations
activeScene        // "intro" | "wizard"
presets            // preset list from /api/setup/presets
lastValidatedConfig // last config that passed backend validation
jsonDraftConfig    // parsed JSON from the advanced editor
jsonDraftValid     // whether the draft passed validation
```

### Data binding

The wizard uses declarative data binding via HTML attributes:

| Attribute | Behavior |
|-----------|----------|
| `data-bind="path.to.field"` | Two-way bind to `configState` via `setAtPath()` |
| `data-options-bind="path"` | Bind comma-separated text to an array in `configState` |
| `data-slug-input="true"` | Slug field — triggers `updateSlugReferences()` on change |
| `data-action="action-name"` | Click handler routed through the action dispatcher |
| `data-help-path="path"` | Shows help popover on hover/focus/click |

The `change` event handler (`workspaceInputHandler`) processes all `data-bind` and `data-options-bind` inputs. It calls `renderAll()` after every change to keep the UI in sync.

The `input` event handler only processes marketplace name/description/industry fields for live-as-you-type updates to the step nav completion indicators.

### Rendering

All rendering is done via `innerHTML` replacement. The `renderAll()` function calls each section renderer:

```
renderAll()
  ├─ renderStepNav()          Step pills with completion badges
  ├─ renderStepPanels()       Show/hide step panels, animate transitions
  ├─ renderPresetList()       Preset cards
  ├─ renderBasics()           Marketplace name/description/industry inputs
  ├─ renderParticipants()     Role cards with permission matrices
  ├─ renderOnboarding()       Onboarding policy per role
  ├─ renderCommunication()    Conversation rule cards
  ├─ renderDiscovery()        Search, filter, AI settings
  ├─ renderSchemas()          Profile field editors (compact inline rows)
  ├─ renderRisks()            Step 7 risk warnings
  └─ renderGlossaryList()     Glossary drawer entries
```

### Slug remapping

When a participant slug is renamed, `updateSlugReferences()` cascades the change:

1. Sanitizes the new slug (lowercase, alphanumeric + underscores).
2. Ensures uniqueness by appending `_2`, `_3`, etc. if needed.
3. Updates `configState.participant_types[index].slug`.
4. Remaps keys in `configState.onboarding`.
5. Remaps keys in `configState.profile_schemas`.
6. Updates all references in `configState.discovery.searchable_types`.
7. Updates all references in `configState.communication.conversation_rules`.

The `setAtPath()` call is skipped for slug inputs — `updateSlugReferences()` handles the full update to avoid overwriting the old slug before the remap reads it.

### Validation error mapping

Backend Pydantic errors are transformed into user-friendly messages by `validation-mapper.js`:

1. Each error has a `loc` array (path) and `msg` string.
2. The mapper checks against a rewrite table (~10 common errors) for friendlier messages.
3. If no rewrite matches, it infers the wizard step from the path prefix (`marketplace` → step 1, `participant_types` → step 2, etc.).
4. Each mapped error gets a "Go to step N" button.

### JSON editor

The advanced JSON editor provides live editing of the raw config:

1. User opens the drawer → current `configState` serialized to JSON.
2. On every keystroke (debounced 350ms) → parse JSON → validate against backend → compute diff.
3. Diff shows added/removed/changed keys grouped by section, with destructive changes flagged.
4. "Apply" merges the validated draft back into `configState` and triggers `renderAll()`.

### CSS layout

The wizard uses a CSS grid shell:

```css
.wizard-shell {
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  /*                   ↑     ↑        ↑          ↑
                    header  errors   body      footer  */
}
```

Key layout details:

- `.wizard-body` and `.wizard-footer` have explicit `grid-row` assignments (3 and 4) to prevent misplacement when the error panel is hidden (`display: none` removes elements from grid flow).
- The body row uses `minmax(0, 1fr)` so it absorbs remaining space and scrolls internally.
- The footer uses `justify-content: space-between` (Previous left, Next right).
- Font loading uses `<link rel="stylesheet">` in the HTML `<head>` with `preconnect` hints, not CSS `@import`.

---

## Adding a new preset

1. Open `app/modules/setup/presets.py`.
2. Add a new dict to the `PRESETS` list with keys: `id`, `title`, `description`, `when_to_use`, `config`.
3. The `config` value must be a full `MarketplaceConfig`-shaped dict.
4. The preset appears automatically in the wizard Step 1 and in `GET /api/setup/presets`.

---

## Adding a new field type

1. Add the type string to the `fieldTypeOptions()` function in `main.js`.
2. Add validation for the new type in `MarketplaceConfig` (Pydantic model).
3. Update the compiler's `render.py` to generate the correct Pydantic field type.
4. Add a help entry in `help-content.js` if the type needs explanation.

---

## Debugging

### Config won't validate

Check the browser console for the raw error response. The `detail.errors` array contains Pydantic validation errors with `loc` (path) and `msg` (message). Common causes:

- Slug referenced in onboarding/schemas/discovery that doesn't match any participant type.
- `select` or `multi_select` field with empty or missing `options`.
- `rag_strict` mode with `vector_search_enabled: false`.

### Generated artifacts out of sync

Run `make compile-check`. If it reports drift, run `make compile` to regenerate. The `spec_hash` in `generated/manifest.json` should match the hash of your current `marketplace.yaml`.

### Wizard won't load

Check that the setup service is running (`make setup-up`) and assets are being served. Open browser devtools Network tab — all asset requests to `/api/setup/assets/*` should return 200.
