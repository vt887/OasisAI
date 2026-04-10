PROJECT_NAME ?= oasis-ai
IMAGE_TAG     ?= latest
SERVICES      := gateway indexer llm graph agent

QUIET_REDIRECT := >/dev/null 2>&1
QUIET_ERR := 2>/dev/null

# ---------------------------------------------------------------------------
# Read versions from version-manager files
#   .python-version  → managed by pyenv / mise  (e.g. "3.12")
#   .tool-versions   → managed by asdf / mise   (e.g. "poetry 2.2.1")
# Fall back to hard-coded defaults when the files are absent.
# ---------------------------------------------------------------------------
_PYTHON_VERSION_RAW := $(shell cat .python-version $(QUIET_ERR) | tr -d '[:space:]')
_POETRY_VERSION_RAW := $(shell grep '^poetry' .tool-versions $(QUIET_ERR) | awk '{print $$2}')

PYTHON_VERSION := $(or $(_PYTHON_VERSION_RAW),3.12)
POETRY_VERSION := $(or $(_POETRY_VERSION_RAW),2.2.1)

# Export so docker-compose picks them up via ${PYTHON_VERSION} / ${POETRY_VERSION}
export PYTHON_VERSION
export POETRY_VERSION

.PHONY: all clean test lint format help setup install versions
all: setup test lint

SHELL := /bin/bash -e

# ============================================================
# Help
# ============================================================

help:
	@echo "OasisAI - developer tasks for local dev & infra"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              Setup project with Poetry"
	@echo "  make install            Install Python dependencies"
	@echo "  make install-prod       Install Python prod dependencies"
	@echo "  make venv               Python venv activation"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format             Format code"
	@echo "  make lint               Run linting"
	@echo "  make format-check       Check formatting without changes"
	@echo "  make actionlint         Validate GitHub Actions workflows"
	@echo ""
	@echo "Testing:"
	@echo "  make test-unit          Run unit tests"
	@echo "  make test-integration   Run integration tests"
	@echo "  make test-coverage      Run tests with coverage (html report)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker (build|up|down|logs|ps)"
	@echo "  make chroma (up|down|logs)"
	@echo "  make ollama (up|down|logs)"
	@echo "  make print-env          Print recommended env vars for local dev"
	@echo ""
	@echo "Orchestration:"
	@echo "  make stack (start|stop|validate|verify)"
	@echo "  make run (gateway|indexer|agent|graph|llm)"
	@echo "  make check-health       Check services /health endpoints"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean              Clean artifacts"
	@echo "  make update-deps        Update Python deps & refresh locks"
	@echo "  make poetry-lock-all    Refresh per-service poetry.lock files"
	@echo ""
	@echo "Versions:"
	@echo "  make versions           Print all resolved versions"

# ============================================================
# Versions
# ============================================================
.PHONY: versions
versions:
	@echo "--- version files ---"
	@echo "Python   : $(PYTHON_VERSION)  (source: .python-version)"
	@echo "Poetry   : $(POETRY_VERSION)  (source: .tool-versions)"
	@echo "Image    : $(PROJECT_NAME):$(IMAGE_TAG)"
	@echo ""
	@echo "--- installed tools ---"
	@command -v docker $(QUIET_REDIRECT) && docker --version || echo "docker: not installed"
	@command -v docker-compose $(QUIET_REDIRECT) && docker-compose --version || echo "docker-compose: not installed"
	@command -v helm $(QUIET_REDIRECT) && helm version || echo "helm: not installed"
	@command -v kubectl $(QUIET_REDIRECT) && kubectl version --client || echo "kubectl: not installed"

# ============================================================
# Setup & Installation
# ============================================================
.PHONY: setup
setup:
	@echo "Setting up..."
	poetry config virtualenvs.in-project true
	poetry lock --no-cache
	poetry install --with dev

.PHONY: install
install:
	@echo "Installing dependencies..."
	poetry config virtualenvs.in-project true
	poetry install --with dev

.PHONY: install-prod
install-prod:
	@echo "Installing production dependencies..."
	poetry config virtualenvs.in-project true
	poetry install --no-dev

# ============================================================
# Code Quality
# ============================================================
.PHONY: format
format:
ifdef CI
	poetry run ruff format --check . && poetry run ruff check .
else
	poetry run ruff format .
	poetry run ruff check --fix .
endif

.PHONY: lint
lint: format
	@echo "Running linting..."
	poetry run mypy services/ shared/ storage/ tests/ scripts/

.PHONY: format-check
format-check:
	@echo "Checking formatting..."
	poetry run ruff format --check .

.PHONY: actionlint
actionlint:
	@echo "Validating GitHub Actions workflows..."
	@which actionlint > /dev/null || { \
		echo "Installing actionlint..."; \
		mkdir -p /tmp/actionlint && \
		wget -q -O /tmp/actionlint/actionlint \
			https://github.com/rhysd/actionlint/releases/download/v1.6.26/actionlint_linux_amd64 && \
		chmod +x /tmp/actionlint/actionlint && \
		sudo mv /tmp/actionlint/actionlint /usr/local/bin/actionlint || \
		echo "Please install actionlint manually: brew install actionlint"; \
	}
	actionlint .github/workflows/*.yml

# ============================================================
# Testing
# ============================================================
.PHONY: test
test: test-unit test-integration

.PHONY: test-unit
test-unit:
	@echo "Running unit tests..."
	poetry run pytest -vvs --cov=services --cov-report xml:.coverage.unit.xml tests/

.PHONY: test-integration
test-integration:
	@echo "Running integration tests..."
	poetry run pytest -vv --cov=services --cov-report xml:.coverage.integration.xml tests/test_integration.py

.PHONY: test-coverage
test-coverage:
	@echo "Running tests with coverage..."
	poetry run pytest tests/ --cov=services --cov=shared --cov-report=html

# ============================================================
# Docker
# ============================================================
COMPOSE := PYTHON_VERSION=$(PYTHON_VERSION) POETRY_VERSION=$(POETRY_VERSION) \
           docker-compose -f compose/docker-compose.yml

.PHONY: docker-build
docker-build:
	@test -n "$(PYTHON_VERSION)" || (echo "[ERROR] PYTHON_VERSION is empty"; exit 1)
	@test -n "$(POETRY_VERSION)" || (echo "[ERROR] POETRY_VERSION is empty"; exit 1)
	@echo "Building Docker images (python=$(PYTHON_VERSION), poetry=$(POETRY_VERSION))..."
	$(COMPOSE) build

.PHONY: docker-up
docker-up:
	@echo "Starting Docker stack..."
	$(COMPOSE) up -d
	@sleep 3
	$(COMPOSE) ps

.PHONY: docker-down
docker-down:
	@echo "Stopping Docker stack..."
	$(COMPOSE) down

.PHONY: docker-logs
docker-logs:
	@echo "Viewing Docker logs..."
	$(COMPOSE) logs -f

.PHONY: docker-clean
docker-clean: docker-down
	@echo "Cleaning Docker resources..."
	$(COMPOSE) rm -v

.PHONY: docker-ps
docker-ps:
	$(COMPOSE) ps

# Convenience dispatcher so you can run "make docker up" instead of
# "make docker-up". Usage: `make docker <up|down|logs|build|ps>`.
# We declare the subcommands as phony no-op targets so Make does not
# error when they are passed as separate goals.
.PHONY: docker up down logs build ps
docker:
	@sub="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$sub" ]; then \
		echo "Usage: make docker <up|down|logs|build|ps>"; exit 1; \
	fi; \
	$(MAKE) docker-$$sub

up:
	@:

down:
	@:

logs:
	@:

build:
	@:

ps:
	@:

.PHONY: chroma ollama
chroma:
	@sub="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$sub" ]; then \
		echo "Usage: make chroma <up|down|logs>"; exit 1; \
	fi; \
	$(MAKE) chroma-$$sub

ollama:
	@sub="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$sub" ]; then \
		echo "Usage: make ollama <up|down|logs>"; exit 1; \
	fi; \
	$(MAKE) ollama-$$sub


# ---------------------------------------------------------------------------
# Helpers to run single infrastructure services (useful for steps 2/3/4)
# ---------------------------------------------------------------------------
.PHONY: chroma-up chroma-down chroma-logs ollama-up ollama-down ollama-logs dev-env print-env

chroma-up:
	@echo "Starting Chroma (via docker-compose)..."
	$(COMPOSE) up -d chroma
	@sleep 2
	$(COMPOSE) ps chroma

chroma-down:
	@echo "Stopping Chroma..."
	$(COMPOSE) stop chroma || true
	$(COMPOSE) rm -f chroma || true

chroma-logs:
	@echo "Tailing Chroma logs..."
	$(COMPOSE) logs -f chroma

ollama-up:
	@echo "Starting Ollama (via docker-compose)..."
	$(COMPOSE) up -d ollama
	@sleep 2
	$(COMPOSE) ps ollama

ollama-down:
	@echo "Stopping Ollama..."
	$(COMPOSE) stop ollama || true
	$(COMPOSE) rm -f ollama || true

ollama-logs:
	@echo "Tailing Ollama logs..."
	$(COMPOSE) logs -f ollama

.PHONY: print-env
print-env:
	@if [ -f .env.local ]; then \
		cat .env.local; \
	else \
		echo ".env.local not found"; \
	fi

# ============================================================
# Development Workflow
# ============================================================
.PHONY: start
start: docker-build docker-up validate
	@echo "✓ System started"

.PHONY: stop
stop: docker-down
	@echo "✓ System stopped"

.PHONY: restart
restart: docker-down docker-up
	@echo "✓ System restarted"

.PHONY: validate
validate:
	@echo "Running validation..."
	python scripts/validate.py

.PHONY: verify
verify:
	@echo "Verifying setup..."
	python scripts/verify_setup.py

# ============================================================
# Dependency Management
# ============================================================
.PHONY: update-deps
update-deps:
	@echo "Updating dependencies..."
	poetry update
	poetry lock

.PHONY: poetry-lock-all
poetry-lock-all:
	@echo "Updating root poetry.lock..."
	poetry lock
	@echo "Updating per-service poetry.lock files..."
	$(foreach service,$(SERVICES), \
		(cd services/$(service) && poetry lock);)

# ============================================================
# Local Development
# ============================================================
.PHONY: venv
shell:
	source .venv/bin/activate

.PHONY: run-gateway
run-gateway:
	@echo "Starting Gateway service..."
	cd services/gateway && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run-indexer
run-indexer:
	@echo "Starting Indexer service..."
	cd services/indexer && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8002

.PHONY: run-agent
run-agent:
	@echo "Starting Agent service..."
	cd services/agent && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8004

.PHONY: run-graph
run-graph:
	@echo "Starting Graph service..."
	cd services/graph && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8003

.PHONY: run-llm
run-llm:
	@echo "Starting LLM service..."
	cd services/llm && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8001

# Convenience dispatcher so you can run "make run gateway" instead of
# "make run-gateway". Usage: `make run <gateway|indexer|agent|graph|llm>`.
.PHONY: run gateway indexer agent graph llm
run:
	@sub="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$sub" ]; then \
		echo "Usage: make run <gateway|indexer|agent|graph|llm>"; exit 1; \
	fi; \
	$(MAKE) run-$$sub

gateway:
	@:

indexer:
	@:

agent:
	@:

graph:
	@:

llm:
	@:

# Dispatcher for stack orchestration (start/stop/validate/logs)
.PHONY: stack
stack:
	@sub="$(word 2,$(MAKECMDGOALS))"; \
	if [ -z "$$sub" ]; then \
		echo "Usage: make stack <start|stop|validate|logs>"; exit 1; \
	fi; \
	case "$$sub" in \
	  logs) $(MAKE) docker-logs ;; \
	  start|stop|validate) $(MAKE) $$sub ;; \
	  *) echo "Unknown stack subcommand: $$sub"; exit 1 ;; \
	esac

# ============================================================
# Maintenance
# ============================================================
.PHONY: clean
clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + $(QUIET_ERR) || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + $(QUIET_ERR) || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + $(QUIET_ERR) || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + $(QUIET_ERR) || true

.PHONY: check-health
check-health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | python -m json.tool $(QUIET_ERR) || echo "Gateway: not responding"
	@curl -s http://localhost:8001/health | python -m json.tool $(QUIET_ERR) || echo "LLM: not responding"
	@curl -s http://localhost:8002/health | python -m json.tool $(QUIET_ERR) || echo "Indexer: not responding"
	@curl -s http://localhost:8003/health | python -m json.tool $(QUIET_ERR) || echo "Graph: not responding"
	@curl -s http://localhost:8004/health | python -m json.tool $(QUIET_ERR) || echo "Agent: not responding"


.DEFAULT_GOAL := help
