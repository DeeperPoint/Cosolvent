# Engines

Engines are stateless, config-driven components in `app/engine/` that interpret the marketplace YAML configuration at runtime. They contain no database access — they operate purely on the `MarketplaceConfig` object and input data.

## Schema Engine (`app/engine/schema_engine.py`)

Generates Pydantic validation models dynamically from profile schema definitions in the marketplace config.

### Functions

#### `get_profile_model(config, type_slug) -> type[BaseModel]`

Returns a dynamically-generated Pydantic `BaseModel` class for the given participant type. The model's fields are derived from the profile schema config:

| Config Field Type | Python Type |
|-------------------|-------------|
| `text` | `str` |
| `number` | `float` |
| `select` | `str` |
| `multi_select` | `list[str]` |
| `date` | `str` |
| `file` | `str` |
| `rich_text` | `str` |
| `location` | `dict` |

Fields marked `required: true` in the config become required model fields. Optional fields default to `None`.

Models are cached per type slug for performance.

#### `validate_profile_fields(config, type_slug, data) -> dict`

Validates a dict of field values against the schema. Returns the validated dict or raises a `ValidationError`.

#### `compute_completeness(config, type_slug, fields) -> int`

Returns a percentage (0–100) representing how many required fields are filled in. Used to enforce `profile_completeness_threshold` during onboarding.

#### `clear_cache()`

Clears the model cache. Called when config changes.

---

## Visibility Engine (`app/engine/visibility_engine.py`)

Controls which profile fields are visible to different viewers.

### Viewer Tiers

| Tier | Who | Sees |
|------|-----|------|
| `anonymous` | Not logged in | `public` fields only |
| `authenticated` | Logged in | `public` + `protected` fields |
| `owner` | Profile owner or admin | All fields including `private` |

### Functions

#### `get_viewer_tier(is_authenticated, is_owner, is_admin) -> ViewerTier`

Determines the viewer tier based on context:
- Admin or profile owner → `"owner"`
- Authenticated user → `"authenticated"`
- Otherwise → `"anonymous"`

#### `filter_fields(schema, fields, viewer_tier) -> dict`

Filters a profile's field values based on the viewer tier and each field's `visibility` setting in the schema. Returns a new dict containing only the fields the viewer is allowed to see.

---

## Permission Engine (`app/engine/permission_engine.py`)

Checks participant permissions and conversation initiation rules from the marketplace config.

### Functions

#### `check_permission(config, type_slug, permission) -> bool`

Checks whether a participant type has a specific permission flag set to `True`. The `permission` string must match a field name on `ParticipantPermissions` (e.g., `"can_search"`, `"can_list"`).

Returns `False` for unknown types or unknown permission names.

#### `can_initiate_conversation(config, initiator_type, receiver_type) -> tuple[bool, bool]`

Checks if one type can start a conversation with another. Returns `(allowed, requires_approval)`:
- Looks up matching `conversation_rules` in the communication config
- If no rule matches, returns `(False, False)`
- If a rule matches, returns `(True, rule.requires_approval)`

#### `get_allowed_conversation_targets(config, initiator_type) -> list[str]`

Returns a list of type slugs that the given initiator type is allowed to start conversations with, based on the communication rules.
