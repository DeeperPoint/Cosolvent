# Contributing

Local development workflow, code style, module conventions, managed zones, and the PR process.

## Prerequisites

Set up your local environment first: [Getting Started](getting-started.md).

## Local Dev Workflow

```bash
# 1. Make changes
# 2. Lint
ruff check app cli tests scripts

# 3. Run unit tests
pytest tests/unit -q

# 4. If you changed marketplace.yaml, recompile
python -m cli compile --config marketplace.yaml --mode mvp

# 5. Compile check (CI gate)
python -m cli compile --check --config marketplace.yaml --mode mvp
```

## Code Style

### Formatting and linting

Use [Ruff](https://docs.astral.sh/ruff/) for both formatting and linting:

```bash
ruff check app cli tests scripts      # lint
ruff format app cli tests scripts     # format
```

Ruff configuration is in `pyproject.toml`.

### Type hints

Use type hints for all public function signatures. Internal helper functions don't need full annotations but should be clear.

### Async

All I/O operations must be async. Database calls, Redis calls, HTTP calls, and file operations use `async`/`await`. Never block the event loop with synchronous I/O.

---

## Module Conventions

Every module in `app/modules/` follows:

```
router.py     ← route definitions only (no logic)
service.py    ← business logic, orchestration
repository.py ← database operations
schemas.py    ← Pydantic request/response models
```

### Router (`router.py`)

- Define route paths and HTTP methods
- Parse request bodies and query params using Pydantic schemas
- Call service functions — no business logic here
- Return responses using response schemas

```python
@router.get("/{type_slug}/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    type_slug: str,
    profile_id: str,
    user: UserDoc | None = Depends(get_current_user_optional),
    config: MarketplaceConfig = Depends(get_marketplace_config),
):
    return await service.get_profile(config, type_slug, profile_id, viewer=user)
```

### Service (`service.py`)

- Contains all business logic
- Calls repositories and engines
- Enqueues background jobs
- Raises domain exceptions (`NotFoundError`, `ForbiddenError`, `ValidationError`)

```python
async def get_profile(config, type_slug, profile_id, viewer):
    profile = await repo.find_one("profiles", {"_id": profile_id})
    if not profile:
        raise NotFoundError(f"Profile {profile_id} not found")
    ...
```

### Repository (`repository.py`)

- Database operations only — no business logic
- Uses the collection API from `app/core/database.py`
- Returns raw documents (dicts)

```python
async def get_profile(profile_id: str) -> dict | None:
    return await db.find_one("profiles", {"_id": profile_id})
```

### Schemas (`schemas.py`)

Pydantic models for:
- Request bodies (`ProfileUpdateRequest`)
- Response models (`ProfileResponse`)
- Internal data structures

---

## Adding a New Module

1. Create `app/modules/{name}/` with `router.py`, `service.py`, `repository.py`, `schemas.py`
2. Register the router in `app/main.py`:
   ```python
   from app.modules.mymodule import router as mymodule_router
   app.include_router(mymodule_router.router, prefix="/api/mymodule", tags=["mymodule"])
   ```
3. Add any new tables to `app/core/database.py` startup initialization
4. Write unit tests in `tests/unit/test_mymodule.py`
5. Write integration tests in `tests/integration/test_mymodule.py`

---

## Managed Zones — What Not to Edit

The compiler writes to these directories. Never hand-edit files in managed zones:

```
app/generated/*
alembic/versions/auto_marketplace_*.py
openapi/generated_openapi.json
generated/manifest.json
exports/*.tar.gz
```

If you need to change the output of generated files, change the compiler (`app/compiler/render.py`) and recompile — not the generated files directly.

If you accidentally edit a managed file, it will be overwritten on the next compile and your changes will be lost.

---

## Config Changes and Regeneration

When you change `marketplace.yaml` (or add support for new config fields):

1. Validate the change: `python -m cli validate marketplace.yaml`
2. Regenerate artifacts: `python -m cli compile --config marketplace.yaml --mode mvp`
3. Commit both the config and the generated files
4. CI compile-check will verify they're in sync

---

## Adding a New Compiler Output

If you need to generate a new file type from the marketplace config:

1. Add IR fields in `app/compiler/ir.py`
2. Add rendering logic in `app/compiler/render.py`
3. Add the output path to the managed zone list in `app/compiler/writer.py`
4. Test that `compile --check` passes with both old and new config

---

## Adding a Wizard Preset

Presets live in `app/modules/setup/presets.py`. Each preset is a dict with:

```python
{
    "id": "my_preset",
    "title": "My Marketplace",
    "description": "Description shown in the wizard",
    "when_to_use": "When to recommend this preset",
    "config": {
        # Full MarketplaceConfig-shaped dict
        "marketplace": {"name": "..."},
        "participant_types": [...],
        "profile_schemas": {...},
        "onboarding": {...},
        "communication": {...},
        "discovery": {...}
    }
}
```

The preset appears automatically in the wizard Step 1 and in `GET /api/setup/presets` after restarting the setup service.

---

## PR Process

1. Fork or branch from `main`
2. Make changes + run the full gate (`make test-all`)
3. Ensure compile-check passes (`make compile-check`)
4. Open a PR with a concise title and description of what changed and why
5. All CI checks must pass before merge

## Commit Style

Concise, imperative first line with bullet-point details for multi-part changes:

```
Add FAQ soft-delete endpoint

- Add is_active flag to FAQ schema
- Filter inactive FAQs from public listing
- Admin endpoint returns all FAQs regardless of is_active
```

## See Also
- [Getting Started](getting-started.md) — environment setup
- [Testing](testing.md) — writing and running tests
- [Architecture](architecture.md) — system design context
- [Compiler](compiler.md) — managed zones in detail

---

[← Testing](testing.md)
