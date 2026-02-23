# Engines

Engines are stateless, config-driven components in `app/engine/` that interpret `MarketplaceConfig` at runtime. They have no database access — they operate purely on the config object and input data.

Three engines exist: permission, schema, and visibility.

---

## Permission Engine (`app/engine/permission_engine.py`)

Checks participant permissions and conversation initiation rules from the marketplace config.

### `check_permission(config, type_slug, permission) -> bool`

Checks whether a participant type has a specific permission flag set to `True`.

```python
from app.engine.permission_engine import check_permission

# Check if "buyer" can search
allowed = check_permission(config, "buyer", "can_search")  # True / False
```

The `permission` string must match a field name on `ParticipantPermissions`:
`can_list`, `can_search`, `can_initiate_conversation`, `can_receive_conversation`, `can_share_private_assets`, `requires_onboarding`, `requires_approval`, `visible_in_search`

Returns `False` for unknown type slugs or unknown permission names.

### `can_initiate_conversation(config, initiator_type, receiver_type) -> tuple[bool, bool]`

Checks if one type can start a conversation with another. Returns `(allowed, requires_approval)`:

```python
allowed, requires_approval = can_initiate_conversation(config, "buyer", "producer")
# (True, True) — buyer can initiate, but producer must accept
```

Looks up matching `conversation_rules` in the communication config. If no rule matches, returns `(False, False)`.

### `get_allowed_conversation_targets(config, initiator_type) -> list[str]`

Returns a list of type slugs that the given type is allowed to start conversations with.

```python
targets = get_allowed_conversation_targets(config, "buyer")
# ["producer"]
```

---

## Schema Engine (`app/engine/schema_engine.py`)

Generates Pydantic validation models dynamically from profile schema definitions in the marketplace config.

### `get_profile_model(config, type_slug) -> type[BaseModel]`

Returns a dynamically-generated Pydantic `BaseModel` class for the given participant type. Fields are derived from the profile schema config.

```python
from app.engine.schema_engine import get_profile_model

ProducerProfile = get_profile_model(config, "producer")
validated = ProducerProfile(**field_data)  # raises ValidationError if invalid
```

**Config type → Python type mapping:**

| Config type | Python type |
|-------------|-------------|
| `text` | `str` |
| `number` | `float` |
| `select` | `str` |
| `multi_select` | `list[str]` |
| `date` | `str` |
| `file` | `str` |
| `rich_text` | `str` |
| `location` | `dict` |

Fields marked `required: true` become required model fields. Optional fields default to `None`.

Models are cached per type slug — generation happens once, then the cache is used on every subsequent call.

### `validate_profile_fields(config, type_slug, data) -> dict`

Validates a dict of field values against the schema. Returns the validated dict or raises `ValidationError`.

```python
from app.engine.schema_engine import validate_profile_fields

validated = validate_profile_fields(config, "producer", {
    "farm_name": "Sunrise Farm",
    "country": "Canada",
    "primary_crops": ["Wheat", "Corn"]
})
```

### `compute_completeness(config, type_slug, fields) -> int`

Returns a percentage (0–100) representing how many required fields are filled in.

```python
from app.engine.schema_engine import compute_completeness

pct = compute_completeness(config, "producer", {"farm_name": "Sunrise Farm"})
# 33 (1 of 3 required fields filled)
```

Used to enforce `profile_completeness_threshold` during onboarding — the user cannot submit until this value meets the threshold.

### `clear_cache()`

Clears the model cache. Called when config changes at runtime (e.g. after a wizard session).

---

## Visibility Engine (`app/engine/visibility_engine.py`)

Controls which profile fields are visible to different viewers.

### Viewer Tiers

| Tier | Who | Can see |
|------|-----|---------|
| `anonymous` | Not logged in | `public` fields only |
| `authenticated` | Logged in | `public` + `protected` fields |
| `owner` | Profile owner or admin | All fields including `private` |

### `get_viewer_tier(is_authenticated, is_owner, is_admin) -> ViewerTier`

Determines the viewer tier based on request context:

```python
from app.engine.visibility_engine import get_viewer_tier

tier = get_viewer_tier(is_authenticated=True, is_owner=False, is_admin=False)
# "authenticated"

tier = get_viewer_tier(is_authenticated=True, is_owner=True, is_admin=False)
# "owner"
```

Rule: admin or profile owner → `"owner"` (regardless of other flags), authenticated user → `"authenticated"`, otherwise → `"anonymous"`.

### `filter_fields(schema, fields, viewer_tier) -> dict`

Filters a profile's field values based on the viewer tier and each field's `visibility` setting in the schema. Returns a new dict containing only the fields the viewer is allowed to see.

```python
from app.engine.visibility_engine import filter_fields

visible = filter_fields(
    schema=config.profile_schemas["producer"],
    fields={"farm_name": "Sunrise", "revenue": 500000},
    viewer_tier="authenticated"
)
# {"farm_name": "Sunrise"}  # revenue is private — filtered out
```

The engine is called in the profiles module before returning any profile response.

---

## How Engines are Used in Practice

A typical profile GET request:

```python
# router.py
@router.get("/{type_slug}/{profile_id}")
async def get_profile(type_slug: str, profile_id: str, user=Depends(get_current_user_optional)):
    profile = await service.get_profile(type_slug, profile_id, viewer=user)
    return profile

# service.py
async def get_profile(type_slug, profile_id, viewer):
    profile = await repo.find_one("profiles", {"_id": profile_id})
    if not profile:
        raise NotFoundError()

    is_owner = viewer and viewer["_id"] == profile["user_id"]
    is_admin = viewer and viewer["role"] == "admin"
    tier = get_viewer_tier(
        is_authenticated=viewer is not None,
        is_owner=is_owner,
        is_admin=is_admin,
    )

    schema = config.profile_schemas[type_slug]
    filtered_fields = filter_fields(schema, profile["fields"], tier)
    return {**profile, "fields": filtered_fields}
```

---

## See Also
- [Architecture](architecture.md) — where engines fit in the system
- [Modules](modules.md) — which modules use which engines
- [Marketplace Config Reference](../user/marketplace-config.md) — visibility and permission options
