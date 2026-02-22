# Testing

## Test Gate

All changes must pass the full gate before merge:

```bash
# 1) Lint
ruff check app cli tests scripts

# 2) Unit
pytest tests/unit -v

# 3) Generated artifacts sync gate
python -m cli compile --check --config marketplace.yaml --mode mvp

# 4) Integration (requires running API/worker/redis/postgres stack)
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -v

# 5) Local full-stack E2E
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -v

# 6) Live-provider E2E (conditional)
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -v -rs
```

Live-provider suite should skip with explicit reasons when required secrets are absent.

Or use Make targets:

```bash
make lint
make unit
make compile-check
make integration
make e2e
make live
make test-all      # lint + unit + integration + e2e
```

## Infrastructure Requirements

- Postgres with `pgvector` extension
- Redis
- API + worker running with matching env

For Docker-based testing, run `make up && make wait-api` before integration/e2e suites.

## Suite Layout

```text
tests/
├── unit/             # Deterministic module/service tests (no infra required)
├── integration/      # API + DB + worker lifecycle tests (requires running stack)
├── e2e/              # Full local stack and live-provider flows
└── test_config/      # Fixture YAML files for marketplace config tests
```

## Test Markers

Custom pytest markers are defined in `pyproject.toml`:

| Marker | Purpose | Requires |
|--------|---------|----------|
| `integration` | Tests that hit the running API/DB/worker stack | `RUN_INTEGRATION=1` |
| `e2e` | Full end-to-end tests against local Docker stack | `RUN_E2E=1` |
| `live` | Tests that call real external providers (OpenAI, Cohere) | `RUN_LIVE_E2E=1` + API keys |

Unit tests have no marker and run without any infrastructure.

## Writing Unit Tests

Unit tests mock all external dependencies (database, Redis, external APIs) and test service logic in isolation.

**Pattern:**

```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
def mock_repo():
    with patch("app.modules.<module>.service.repo") as mock:
        yield mock

@pytest.mark.asyncio
async def test_something(mock_repo):
    mock_repo.some_method = AsyncMock(return_value={"_id": "abc", ...})
    result = await service.some_method("abc")
    assert result["id"] == "abc"
```

**Conventions:**

- Mock at the repository layer (`service.repo`), not at the database layer
- Use `AsyncMock` for all async repository methods
- Test both the success path and the error path (e.g. `NotFoundError`)
- Group related tests into classes (e.g. `TestCreateUser`, `TestDeleteUser`)
- Use `_fake_*` helper functions for fixture data

## Writing Integration Tests

Integration tests run against the live Docker stack and verify end-to-end API behavior.

```python
import pytest
import httpx

BASE_URL = os.environ.get("INTEGRATION_BASE_URL", "http://localhost:18000")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_signup_and_login():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await client.post("/api/auth/signup", json={...})
        assert resp.status_code == 200
```

Integration tests are gated behind `RUN_INTEGRATION=1` and skipped otherwise.

## Core Scenarios Covered

- Signup -> draft -> submit -> admin approve -> active profile
- Document upload -> queued processing -> terminal status
- Discovery visibility/filter behavior
- Conversation request -> accept -> message + notifications
- Deactivated user denied on authenticated endpoints
- WebSocket auth + ping/pong + message broadcast

## Running Tests in CI

GitHub Actions runs lint + unit tests on every push and PR. Integration and E2E tests require the Docker stack and are run locally or in dedicated CI environments.

See `.github/workflows/ci.yml` for the CI configuration.
