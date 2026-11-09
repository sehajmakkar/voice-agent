.PHONY: help install lint format test check up down logs

COMPOSE := docker compose -f infra/docker-compose.yml

help:  ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

install:  ## Install dependencies and the git pre-commit hook
	uv sync
	uv run pre-commit install

lint:  ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-fix lint issues and format code
	uv run ruff check --fix .
	uv run ruff format .

test:  ## Run the test suite
	uv run pytest

check: lint test  ## Everything CI will run

up:  ## Start Postgres, Jaeger and Grafana
	$(COMPOSE) up -d

down:  ## Stop local infrastructure (data is kept)
	$(COMPOSE) down

logs:  ## Follow infrastructure logs
	$(COMPOSE) logs -f
