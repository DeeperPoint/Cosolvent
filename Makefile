SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
UVICORN := $(VENV)/bin/uvicorn
ARQ := $(VENV)/bin/arq

API_HOST_PORT ?= 18000
SETUP_HOST_PORT ?= 18080
POSTGRES_HOST_PORT ?= 15432
INTEGRATION_BASE_URL ?= http://localhost:$(API_HOST_PORT)
E2E_BASE_URL ?= http://localhost:$(API_HOST_PORT)
ADMIN_EMAIL ?= admin@example.com
ADMIN_PASSWORD ?= ChangeMe123!
DOCKER_BUILD_ENV := DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1

.PHONY: help venv install lint lint-fix unit integration e2e live test-all \
	docker-cache setup-up setup-down up down reset ps logs logs-api logs-worker wait-api bootstrap-admin \
	api worker validate-config wizard onboarding smoke-setup

help: ## Show available commands
	@echo "Cosolvent Make Targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | awk 'BEGIN {FS = ":.*## "}; {printf "  %-18s %s\n", $$1, $$2}'

venv: ## Create Python virtual environment
	python3 -m venv $(VENV)

install: venv ## Install project + dev dependencies into .venv
	$(PIP) install -e ".[dev]"

lint: ## Run Ruff lint checks
	$(RUFF) check app cli tests scripts

lint-fix: ## Run Ruff with auto-fixes
	$(RUFF) check --fix app cli tests scripts

unit: ## Run unit tests
	$(PYTEST) tests/unit -q

integration: ## Run integration tests (requires running stack)
	RUN_INTEGRATION=1 INTEGRATION_BASE_URL=$(INTEGRATION_BASE_URL) $(PYTEST) tests/integration -q

e2e: ## Run local full-stack E2E (requires running stack)
	RUN_E2E=1 E2E_BASE_URL=$(E2E_BASE_URL) $(PYTEST) tests/e2e/test_local_full_stack.py -q

live: ## Run live-provider E2E (uses .env secrets if present)
	set -a; [ -f .env ] && source .env; set +a; \
	RUN_LIVE_E2E=1 E2E_BASE_URL=$(E2E_BASE_URL) $(PYTEST) tests/e2e/test_live_providers.py -q -rs

test-all: lint unit integration e2e ## Run lint + unit + integration + local E2E

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
	$(PYTHON) scripts/wait_for_http.py --url http://localhost:$(API_HOST_PORT)/api/health --timeout 180

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

bootstrap-admin: ## Bootstrap first admin user via API
	curl -sS -X POST http://localhost:$(API_HOST_PORT)/api/auth/bootstrap \
		-H "Content-Type: application/json" \
		-d '{"email":"$(ADMIN_EMAIL)","password":"$(ADMIN_PASSWORD)"}' | $(PYTHON) -m json.tool

api: ## Run API locally (non-Docker)
	set -a; [ -f .env ] && source .env; set +a; \
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run worker locally (non-Docker)
	set -a; [ -f .env ] && source .env; set +a; \
	$(ARQ) app.workers.settings.WorkerSettings

validate-config: ## Validate marketplace config file (uses marketplace.example.yaml by default)
	$(PYTHON) -m cli validate marketplace.example.yaml

wizard: ## Launch CLI onboarding wizard
	$(PYTHON) -m cli wizard -o marketplace.yaml

onboarding: ## Open web onboarding URL hint
	@echo "Setup service onboarding: http://localhost:$(SETUP_HOST_PORT)/onboarding"
	@echo "API onboarding (when API is running): http://localhost:$(API_HOST_PORT)/onboarding"

smoke-setup: ## Smoke test setup APIs (onboarding backend)
	$(PYTHON) -c "import json, urllib.request; base='http://localhost:$(API_HOST_PORT)'; html=urllib.request.urlopen(base+'/onboarding').read().decode('utf-8'); assert 'Configure' in html; cfg=json.loads(urllib.request.urlopen(base+'/api/setup/config-template').read().decode('utf-8'))['config']; req=urllib.request.Request(base+'/api/setup/validate', data=json.dumps({'config': cfg}).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST'); res=json.loads(urllib.request.urlopen(req).read().decode('utf-8')); assert res.get('valid') is True; print('setup smoke ok')"
