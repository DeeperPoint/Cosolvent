# Testing

Test strategy, suite layout, fixtures, and how to run each tier.

## Three Tiers

| Tier | Directory | Requires | Speed |
|------|-----------|---------|-------|
| Unit | `tests/unit/` | Nothing (no infra) | Fast |
| Integration | `tests/integration/` | Running API + DB + worker | Medium |
| E2E | `tests/e2e/` | Running Docker stack | Slow |

## Full Gate

Run this before every PR merge:

```bash
# 1. Lint
ruff check app cli tests scripts

# 2. Unit tests
pytest tests/unit -v

# 3. Compile-check (generated artifact sync)
python -m cli compile --check --config marketplace.yaml --mode mvp

# 4. Integration tests
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -v

# 5. Full-stack E2E
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -v

# 6. Live-provider E2E (conditional — only when API keys present)
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -v -rs
```

Or via Make:

```bash
make lint
make unit
make compile-check
make integration      # requires make up && make wait-api first
make e2e
make live
make test-all         # lint + unit + integration + e2e
```

## Suite Layout

```
tests/
├── unit/             # Deterministic module/service tests (no infra)
├── integration/      # API + DB + worker lifecycle tests
├── e2e/
│   ├── test_local_full_stack.py   # Full flow against Docker stack
│   └── test_live_providers.py     # Calls real AI providers
└── test_config/      # Fixture YAML files for marketplace config tests
```

## Test Markers

Custom markers are defined in `pyproject.toml`:

| Marker | Gate env var | Purpose |
|--------|-------------|---------|
| `integration` | `RUN_INTEGRATION=1` | Tests that hit the live API/DB/worker |
| `e2e` | `RUN_E2E=1` | Full end-to-end tests against Docker stack |
| `live` | `RUN_LIVE_E2E=1` | Tests that call real external providers (OpenAI, etc.) |

Unit tests have no marker and run without any environment variable or infrastructure.

## Infrastructure for Integration and E2E

Start the stack before running integration or E2E tests:

```bash
make up
make wait-api
```

The Docker stack must be running at the target base URL (`INTEGRATION_BASE_URL` / `E2E_BASE_URL`).

## Writing Unit Tests

Unit tests mock all external dependencies (database, Redis, external APIs) and test service logic in isolation.

**Pattern:**

```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
def mock_repo():
    with patch("app.modules.profiles.service.repo") as mock:
        yield mock

@pytest.mark.asyncio
async def test_get_profile_not_found(mock_repo):
    mock_repo.find_one = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await service.get_profile("producer", "nonexistent-id")
```

**Conventions:**
- Mock at the repository layer (`service.repo`), not at the database layer
- Use `AsyncMock` for all async repository methods
- Test both success and error paths
- Group related tests into classes (e.g. `TestGetProfile`, `TestUpdateProfile`)
- Use `_fake_*` helpers for fixture data construction

**Fixture data helpers** (defined per test file or in `conftest.py`):

```python
def _fake_profile(participant_type="producer", status="active"):
    return {
        "_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "participant_type": participant_type,
        "status": status,
        "fields": {"farm_name": "Test Farm"},
        "completeness": 100,
    }
```

## Writing Integration Tests

Integration tests run against the live Docker stack and verify end-to-end API behavior.

```python
import os
import pytest
import httpx

BASE_URL = os.environ.get("INTEGRATION_BASE_URL", "http://localhost:18000")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_signup_and_profile_flow():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Signup
        resp = await client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "Password123!",
            "participant_type": "producer"
        })
        assert resp.status_code == 200
        cookies = resp.cookies

        # Get draft
        resp = await client.get("/api/profiles/producer/draft", cookies=cookies)
        assert resp.status_code == 200
```

Integration tests are skipped automatically unless `RUN_INTEGRATION=1`.

## Core Scenarios Covered

The integration suite covers these flows end-to-end:

- Signup → draft → update fields → submit → admin approve → active profile
- Document upload → background processing → terminal status (indexed or failed)
- Discovery: visibility filter behavior (anonymous vs. authenticated results)
- Conversation: request → accept → send message → notification created
- User deactivation: deactivated user denied on authenticated endpoints
- WebSocket: auth → ping/pong → message broadcast → edit → delete

## Live Provider Tests

```bash
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -v -rs
```

These tests call real AI providers (OpenAI, etc.) and are only meaningful when the corresponding API keys are configured. They skip with explicit reasons when secrets are absent:

```python
@pytest.mark.live
async def test_rag_query():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    ...
```

## Test Config Fixtures

`tests/test_config/` contains YAML fixtures for marketplace config tests. These are used by unit tests that test the compiler, engines, or config validation.

```
tests/test_config/
├── valid_minimal.yaml     # Minimum valid config
├── valid_full.yaml        # Full config with all options set
└── invalid_*.yaml         # Configs expected to fail validation
```

## CI Configuration

GitHub Actions runs lint + unit tests on every push and PR (`.github/workflows/ci.yml`). Integration and E2E tests require the Docker stack and are run locally or in dedicated CI environments with more resources.

## See Also
- [Getting Started](getting-started.md) — running tests locally
- [Contributing](contributing.md) — what tests to add for new features
