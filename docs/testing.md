# Testing

## Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Specific test file
pytest tests/unit/test_admin_service.py -v

# Specific test class
pytest tests/unit/test_admin_service.py::TestGetUser -v
```

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_config/                   # YAML fixture configs
│   ├── agriculture.yaml           # Full agriculture marketplace
│   ├── talent.yaml                # 3-type talent marketplace
│   └── minimal.yaml               # Minimal valid config
├── unit/
│   ├── test_marketplace_config.py # Config loading & cross-validation
│   ├── test_schema_engine.py      # Dynamic model generation
│   ├── test_visibility_engine.py  # Field visibility filtering
│   ├── test_permission_engine.py  # Permission & conversation rules
│   ├── test_admin_service.py      # Admin service layer
│   ├── test_cli_validate.py       # CLI validate command
│   └── test_cli_review_generate.py # Wizard review step
├── integration/                   # Integration tests (placeholder)
└── e2e/                           # End-to-end tests (placeholder)
```

## Test Fixtures

### YAML Configs (`tests/test_config/`)

- **`agriculture.yaml`** — Full config for a grain marketplace with 2 types (producer, buyer), multiple visibility tiers, AI features enabled.
- **`talent.yaml`** — 3-type marketplace (recruiter, candidate, agency) with multiple conversation rules.
- **`minimal.yaml`** — Bare minimum valid config with AI features disabled.

### Access Pattern

```python
FIXTURES = Path(__file__).parent.parent / "test_config"
cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
```

## Test Categories

### Config Validation Tests (`test_marketplace_config.py`)

Tests loading valid configs, verifying parsed values, and ensuring cross-validation catches invalid configs:
- Valid configs load correctly (agriculture, talent, minimal)
- Participant type access and permissions
- Profile schema fields, types, visibility tiers
- Onboarding settings per type
- Communication rules
- Discovery settings
- Negative tests: too few/many types, missing schemas, bad references, missing options

### Engine Tests

**`test_schema_engine.py`** — Dynamic Pydantic model generation:
- Model creation per type slug
- Required field enforcement
- Type validation (text→str, number→float, etc.)
- Unknown type handling

**`test_visibility_engine.py`** — Field filtering:
- Anonymous sees public only
- Authenticated sees public + protected
- Owner sees all
- Missing fields not included

**`test_permission_engine.py`** — Permission checks:
- Per-type permission flags
- Conversation initiation rules
- Multi-rule configs (talent marketplace)
- Allowed target listing

### Admin Service Tests (`test_admin_service.py`)

Mock-based tests for the admin service layer:
- User CRUD: get (found/not found), role update, deactivate, activate
- FAQ CRUD: create, list, get, delete, not-found handling
- Profile override: get full profile, not-found
- Conversation oversight: list all conversations

Pattern: mock the repository with `AsyncMock`, verify service raises `NotFoundError` when repo returns `None`.

### CLI Tests

**`test_cli_validate.py`** — Config file validation:
- Valid configs return `True` (agriculture, minimal, talent)
- Nonexistent path returns `False`

**`test_cli_review_generate.py`** — Review step:
- Confirm returns `True`
- Deny returns `False`
- Ctrl+C (KeyboardInterrupt) returns `False`
- `None` result returns `False`

Pattern: mock `questionary.confirm` to control user input.

## Writing New Tests

### Unit Test Pattern (Service Layer)

```python
from unittest.mock import AsyncMock, patch
import pytest
from app.core.exceptions import NotFoundError

@pytest.fixture
def mock_repo():
    with patch("app.modules.mymodule.service.repo") as mock:
        yield mock

class TestMyFunction:
    @pytest.mark.asyncio
    async def test_success(self, mock_repo):
        mock_repo.get_thing = AsyncMock(return_value={"_id": "123", "name": "test"})
        result = await service.get_thing("123")
        assert result["id"] == "123"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_repo):
        mock_repo.get_thing = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.get_thing("nonexistent")
```

### Unit Test Pattern (CLI)

```python
from unittest.mock import patch, MagicMock

class TestMyStep:
    @patch("cli.steps.mystep.questionary")
    def test_user_confirms(self, mock_q):
        mock_confirm = MagicMock()
        mock_confirm.ask.return_value = True
        mock_q.confirm.return_value = mock_confirm
        assert my_step_function(data) is True
```

## Configuration

Test settings in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

The `asyncio_mode = "auto"` setting means `@pytest.mark.asyncio` is optional but explicit marking is recommended for clarity.
