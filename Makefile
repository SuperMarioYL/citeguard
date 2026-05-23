# CiteGuard — developer tasks
#
# Tiny on purpose: lint and tests should be runnable without remembering flags.
# Keep new targets self-documenting via `## help text` so `make help` stays useful.

.DEFAULT_GOAL := help

PY ?= python
RUFF ?= ruff

.PHONY: help install-dev lint lint-fix test

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-dev: ## Install the package + dev extras in editable mode.
	$(PY) -m pip install -e ".[dev]"

lint: ## Run ruff check + ruff format --check (pre-release smoke gate).
	$(RUFF) check .
	$(RUFF) format --check .

lint-fix: ## Auto-fix lint issues and re-format in place.
	$(RUFF) check --fix .
	$(RUFF) format .

test: ## Run the test suite.
	pytest -q
