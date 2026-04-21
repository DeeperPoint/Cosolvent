# Convenience when your shell cwd is frontend/ (root Makefile lives one level up).
PYTHON := .venv/bin/python

.PHONY: install generate generate-clean dev

install: ## Create venv and install compiler package
	python3 -m venv .venv
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e "compiler[dev]"

generate: ## Regenerate Next.js from OpenAPI + marketplace (keeps hand-edited non-generated files)
	$(PYTHON) -m compiler generate \
		--openapi ../openapi/generated_openapi.json \
		--marketplace ../marketplace.yaml \
		--output .

generate-clean: ## Regenerate and overwrite scaffold + app files
	$(PYTHON) -m compiler generate \
		--openapi ../openapi/generated_openapi.json \
		--marketplace ../marketplace.yaml \
		--output . \
		--clean

dev: ## Run Next.js dev server (run npm install first)
	npm run dev
