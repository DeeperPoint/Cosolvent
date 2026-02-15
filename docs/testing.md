# Testing

## Test Gate

```bash
# 1) Lint
ruff check app cli tests scripts

# 2) Unit
pytest tests/unit -v

# 3) Integration (requires running API/worker/redis/postgres stack)
RUN_INTEGRATION=1 INTEGRATION_BASE_URL=http://localhost:18000 pytest tests/integration -v

# 4) Local full-stack E2E
RUN_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_local_full_stack.py -v

# 5) Live-provider E2E (conditional)
RUN_LIVE_E2E=1 E2E_BASE_URL=http://localhost:18000 pytest tests/e2e/test_live_providers.py -v -rs
```

Live-provider suite should skip with explicit reasons when required secrets are absent.

## Infrastructure Requirements

- Postgres with `pgvector`
- Redis
- API + worker running with matching env

## Suite Layout

```text
tests/
├── unit/         # deterministic module/service tests
├── integration/  # API + DB + worker lifecycle tests
└── e2e/          # full local stack and live-provider flows
```

## Core Scenarios Covered

- Signup -> draft -> submit -> admin approve -> active profile
- Document upload -> queued processing -> terminal status
- Discovery visibility/filter behavior
- Conversation request -> accept -> message + notifications
- Deactivated user denied on authenticated endpoints
- WebSocket auth + ping/pong + message broadcast
