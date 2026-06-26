SHELL := /bin/bash
.DEFAULT_GOAL := help

# Backend venv paths (relative to backend/ since all commands cd there)
BE_PYTHON := .venv/bin/python
BE_PIP := .venv/bin/pip
BE_PYTEST := .venv/bin/pytest
BE_RUFF := .venv/bin/ruff
BE_UVICORN := .venv/bin/uvicorn
BE_ARQ := .venv/bin/arq

# Frontend venv paths (relative to frontend/)
FE_PYTHON := .venv/bin/python
FE_PYTEST := .venv/bin/pytest

API_HOST_PORT ?= 18000
SETUP_HOST_PORT ?= 18080
POSTGRES_HOST_PORT ?= 15432
INTEGRATION_BASE_URL ?= http://localhost:$(API_HOST_PORT)
E2E_BASE_URL ?= http://localhost:$(API_HOST_PORT)
ADMIN_EMAIL ?= admin@example.com
ADMIN_PASSWORD ?= $(error Set ADMIN_PASSWORD env var before running bootstrap-admin)
DOCKER_BUILD_ENV := DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1

.PHONY: help venv install install-frontend lint lint-fix format type-check clean \
	unit unit-frontend integration e2e live test-all \
	docker-cache setup-up setup-down up down reset ps logs logs-api logs-worker wait-api bootstrap-admin \
	api worker validate-config wizard gen-config build-from-docs live-from-docs load-knowledge onboarding smoke-setup compile compile-check export postman-export regenerate-auto \
	generate-frontend

help: ## Show available commands
	@echo "Cosolvent Make Targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | awk 'BEGIN {FS = ":.*## "}; {printf "  %-20s %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────

venv: ## Create Python virtual environment for backend
	cd backend && python3 -m venv .venv

install: venv ## Install backend + dev dependencies into backend/.venv
	cd backend && $(BE_PIP) install -e ".[dev]"

install-frontend: ## Install frontend compiler deps into frontend venv
	cd frontend && python3 -m venv .venv && .venv/bin/pip install -e "compiler[dev]"

# ── Lint & Format (backend) ──────────────────────────────────────────

lint: ## Run Ruff lint checks on backend
	cd backend && $(BE_RUFF) check app cli tests scripts

lint-fix: ## Run Ruff with auto-fixes on backend
	cd backend && $(BE_RUFF) check --fix app cli tests scripts

format: ## Format backend code with Ruff
	cd backend && $(BE_RUFF) format app cli tests scripts

type-check: ## Run mypy type checking on backend
	cd backend && .venv/bin/mypy app cli --ignore-missing-imports

clean: ## Remove build artifacts and caches
	rm -rf backend/dist/ backend/*.egg-info/ backend/.pytest_cache/ backend/.ruff_cache/ backend/.mypy_cache/
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find frontend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── Testing ───────────────────────────────────────────────────────────

unit: ## Run backend unit tests
	cd backend && MARKETPLACE_CONFIG_PATH=../marketplace.yaml $(BE_PYTEST) tests/unit -q

unit-frontend: ## Run frontend compiler unit tests
	cd frontend && $(FE_PYTEST) compiler/tests -q

integration: ## Run integration tests (requires running stack)
	cd backend && RUN_INTEGRATION=1 INTEGRATION_BASE_URL=$(INTEGRATION_BASE_URL) $(BE_PYTEST) tests/integration -q

e2e: ## Run local full-stack E2E (requires running stack)
	cd backend && RUN_E2E=1 E2E_BASE_URL=$(E2E_BASE_URL) $(BE_PYTEST) tests/e2e/test_local_full_stack.py tests/e2e/test_onboarding_experience.py -q

live: ## Run live-provider E2E (uses .env secrets if present)
	cd backend && set -a; [ -f ../.env ] && source ../.env; set +a; \
	RUN_LIVE_E2E=1 E2E_BASE_URL=$(E2E_BASE_URL) $(BE_PYTEST) tests/e2e/test_live_providers.py -q -rs

test-all: lint unit unit-frontend integration e2e ## Run lint + unit + integration + local E2E

# ── Docker ────────────────────────────────────────────────────────────

docker-cache: ## Build app images and warm local Docker cache
	@if [ -f .env ]; then \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env build setup api worker; \
	else \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose build setup api worker; \
	fi

setup-up: ## Start setup/onboarding service only (no DB/API required)
	@if [ -f .env ]; then \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env up -d --build setup; \
	else \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose up -d --build setup; \
	fi

up: ## Start Docker stack (Postgres+Redis+API+worker)
	@if [ -f .env ]; then \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env up -d --build; \
	else \
		$(DOCKER_BUILD_ENV) API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose up -d --build; \
	fi

wait-api: ## Wait for API health endpoint to be ready
	cd backend && $(BE_PYTHON) scripts/wait_for_http.py --url http://localhost:$(API_HOST_PORT)/api/health --timeout 180

down: ## Stop Docker stack
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env down; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose down; \
	fi

setup-down: ## Stop setup/onboarding service only
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env stop setup; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose stop setup; \
	fi

reset: ## Stop Docker stack and remove volumes
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env down -v --remove-orphans; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose down -v --remove-orphans; \
	fi

ps: ## Show Docker stack status
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env ps; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose ps; \
	fi

logs: ## Tail all Docker logs
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env logs -f; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose logs -f; \
	fi

logs-api: ## Tail API logs
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env logs -f api; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose logs -f api; \
	fi

logs-worker: ## Tail worker logs
	@if [ -f .env ]; then \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose --env-file .env logs -f worker; \
	else \
		API_HOST_PORT=$(API_HOST_PORT) SETUP_HOST_PORT=$(SETUP_HOST_PORT) POSTGRES_HOST_PORT=$(POSTGRES_HOST_PORT) docker compose logs -f worker; \
	fi

# ── Local dev (non-Docker) ───────────────────────────────────────────

bootstrap-admin: ## Bootstrap first admin user via API
	curl -sS -X POST http://localhost:$(API_HOST_PORT)/api/auth/bootstrap \
		-H "Content-Type: application/json" \
		-d '{"email":"$(ADMIN_EMAIL)","password":"$(ADMIN_PASSWORD)"}' | python3 -m json.tool

api: ## Run API locally (non-Docker)
	cd backend && set -a; [ -f ../.env ] && source ../.env; set +a; \
	$(BE_UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run worker locally (non-Docker)
	cd backend && set -a; [ -f ../.env ] && source ../.env; set +a; \
	$(BE_ARQ) app.workers.settings.WorkerSettings

# ── CLI commands ──────────────────────────────────────────────────────

validate-config: ## Validate marketplace config file (uses marketplace.example.yaml by default)
	cd backend && $(BE_PYTHON) -m cli validate ../marketplace.example.yaml

wizard: ## Launch CLI onboarding wizard
	cd backend && $(BE_PYTHON) -m cli wizard -o ../marketplace.yaml

SCHEMA ?= ../../CommonContext/schemas/grain_trade_schema.yaml
GEN_OUT ?= ../marketplace.yaml
gen-config: ## Generate marketplace.yaml from a domain schema via Claude/OpenRouter (override SCHEMA=, GEN_OUT=, MODEL=)
	cd backend && $(BE_PYTHON) -m configgen --domain-schema $(SCHEMA) -o $(GEN_OUT) $(if $(MODEL),--model $(MODEL),)

CC_DIR ?= ../CommonContext
GEN_SCHEMA ?= schemas/generated_schema.yaml
# Host CLI must target the Docker Postgres (published on $(POSTGRES_HOST_PORT)),
# NOT a local :5432 — otherwise load-references silently hits the wrong server.
HOST_POSTGRES_DSN ?= postgresql+asyncpg://postgres:postgres@localhost:$(POSTGRES_HOST_PORT)/cosolvent
build-from-docs: ## Build marketplace + backend from ALL CommonContext/inputs/ docs: synth schema -> marketplace.yaml -> compile -> (load knowledge if embeddable). Override MODEL=.
	@echo "==> [1/4] CommonContext: convert inputs/ -> synthesize schema (+ knowledge if OPENAI_API_KEY)"
	cd $(CC_DIR) && .venv/bin/python build_from_inputs.py --out-schema $(GEN_SCHEMA) --refs-out generated_refs.jsonl $(if $(MODEL),--model $(MODEL),)
	@echo "==> [2/4] Cosolvent: generate marketplace.yaml from the synthesized schema"
	cd backend && $(BE_PYTHON) -m configgen --domain-schema ../$(CC_DIR)/$(GEN_SCHEMA) -o ../marketplace.yaml $(if $(MODEL),--model $(MODEL),)
	@echo "==> [3/4] Cosolvent: compile backend artifacts"
	cd backend && $(BE_PYTHON) -m cli compile --config ../marketplace.yaml --mode mvp
	@echo "==> [4/4] Cosolvent: load knowledge library (only if generated and stack is up)"
	@if [ -f $(CC_DIR)/generated_refs.jsonl ]; then \
		vert=$$(grep -E '^vertical:' $(CC_DIR)/$(GEN_SCHEMA) | head -1 | sed 's/^vertical:[[:space:]]*//'); \
		echo "    loading reference_library (vertical=$$vert) — needs the stack running (make up)"; \
		cd backend && POSTGRES_DSN='$(HOST_POSTGRES_DSN)' $(BE_PYTHON) -m cli load-references ../$(CC_DIR)/generated_refs.jsonl --vertical $$vert \
			|| echo "    !! knowledge load failed — is the stack up (make up)? Re-run 'make load-knowledge' once healthy."; \
	else \
		echo "    no generated_refs.jsonl — knowledge library skipped (no embedding key)."; \
	fi
	@echo "==> done. To serve the new marketplace live: make reset && make up && make wait-api"

load-knowledge: ## Load CommonContext's generated_refs.jsonl into the RUNNING stack (DSN pinned to :$(POSTGRES_HOST_PORT))
	@if [ ! -f $(CC_DIR)/generated_refs.jsonl ]; then echo "no $(CC_DIR)/generated_refs.jsonl — run 'make build-from-docs' first"; exit 1; fi
	@vert=$$(grep -E '^vertical:' $(CC_DIR)/$(GEN_SCHEMA) | head -1 | sed 's/^vertical:[[:space:]]*//'); \
		echo "Loading reference_library (vertical=$${vert:-<from records>}) via $(HOST_POSTGRES_DSN)"; \
		cd backend && POSTGRES_DSN='$(HOST_POSTGRES_DSN)' $(BE_PYTHON) -m cli load-references ../$(CC_DIR)/generated_refs.jsonl $${vert:+--vertical $$vert}

live-from-docs: ## FULL end-to-end: inputs/ -> schema+knowledge -> marketplace.yaml -> compile -> fresh stack -> load knowledge -> live APIs. Override MODEL=.
	@echo "==> [1/5] CommonContext: synthesize schema (+ knowledge library) from inputs/"
	cd $(CC_DIR) && .venv/bin/python build_from_inputs.py --out-schema $(GEN_SCHEMA) --refs-out generated_refs.jsonl $(if $(MODEL),--model $(MODEL),)
	@echo "==> [2/5] Cosolvent: generate marketplace.yaml from the schema"
	cd backend && $(BE_PYTHON) -m configgen --domain-schema ../$(CC_DIR)/$(GEN_SCHEMA) -o ../marketplace.yaml $(if $(MODEL),--model $(MODEL),)
	@echo "==> [3/5] Cosolvent: compile backend API artifacts from marketplace.yaml"
	cd backend && $(BE_PYTHON) -m cli compile --config ../marketplace.yaml --mode mvp
	@echo "==> [4/5] Cosolvent: bring up a FRESH stack with the new config (reset wipes old data)"
	$(MAKE) reset && $(MAKE) up && $(MAKE) wait-api
	@echo "==> [5/5] Cosolvent: load the knowledge library into the running stack"
	$(MAKE) load-knowledge
	@echo ""
	@echo "==> LIVE — open Swagger at http://localhost:$(API_HOST_PORT)/docs"

compile: ## Generate backend marketplace artifacts from marketplace.yaml
	cd backend && $(BE_PYTHON) -m cli compile --config ../marketplace.yaml --mode mvp

compile-check: ## Verify generated artifacts are in sync with marketplace.yaml
	cd backend && $(BE_PYTHON) -m cli compile --check --config ../marketplace.yaml --mode mvp

export: ## Generate artifacts and export deployable package
	cd backend && $(BE_PYTHON) -m cli export --config ../marketplace.yaml --mode mvp --export-dir exports

postman-export: ## Export Postman collection from OpenAPI
	cd backend && $(BE_PYTHON) scripts/export_postman_collection.py --out postman/Cosolvent-API.postman_collection.json

generate-frontend: ## Generate Next.js frontend from OpenAPI + marketplace.yaml
	cd frontend && $(FE_PYTHON) -m compiler generate \
		--openapi ../openapi/generated_openapi.json \
		--marketplace ../marketplace.yaml \
		--output .

# ── Full pipeline ─────────────────────────────────────────────────────

regenerate-auto: ## Full reset + regenerate + health + core gates
	$(MAKE) reset
	$(MAKE) compile
	$(MAKE) up
	$(MAKE) wait-api
	$(MAKE) compile-check
	$(MAKE) integration
	$(MAKE) e2e

onboarding: ## Open web onboarding URL hint
	@echo "Setup service onboarding: http://localhost:$(SETUP_HOST_PORT)/onboarding"
	@echo "API onboarding (when API is running): http://localhost:$(API_HOST_PORT)/onboarding"

smoke-setup: ## Smoke test setup APIs (onboarding backend)
	cd backend && $(BE_PYTHON) -c "import json, urllib.request; base='http://localhost:$(API_HOST_PORT)'; html=urllib.request.urlopen(base+'/onboarding').read().decode('utf-8'); assert 'Configure' in html; cfg=json.loads(urllib.request.urlopen(base+'/api/setup/config-template').read().decode('utf-8'))['config']; req=urllib.request.Request(base+'/api/setup/validate', data=json.dumps({'config': cfg}).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST'); res=json.loads(urllib.request.urlopen(req).read().decode('utf-8')); assert res.get('valid') is True; print('setup smoke ok')"
