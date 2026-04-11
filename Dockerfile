# ============================================================
# OasisAI — Multistage root Dockerfile
# Build any service with: docker build --target <service> .
# Used by compose/docker-compose.yml via `context: ..`
#
# Versions are driven by repo version files:
#   .python-version  → PYTHON_VERSION (e.g. 3.12)
#   .tool-versions   → POETRY_VERSION (e.g. 2.2.1)
# ============================================================

# Declared before FROM so they can be used in FROM itself
ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=2.2.1

FROM python:${PYTHON_VERSION}-slim AS base
# Re-declare ARGs inside the stage so they are in scope for RUN instructions
ARG POETRY_VERSION
WORKDIR /app
COPY shared/ ./shared/
COPY storage/ ./storage/
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"
RUN poetry config virtualenvs.create false

# ============================================================
# Dev / test image — uses root pyproject
# ============================================================
FROM base AS development
COPY pyproject.toml poetry.lock ./
RUN poetry install --with dev --no-interaction --no-ansi
COPY . .
CMD ["python", "-m", "pytest", "tests/"]

# ============================================================
FROM base AS gateway
COPY services/gateway/pyproject.toml services/gateway/poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi
COPY services/gateway/ .
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================
FROM base AS indexer
COPY services/indexer/pyproject.toml services/indexer/poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi
COPY services/indexer/ .
VOLUME ["/repos"]
EXPOSE 8002
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

# ============================================================
FROM base AS llm
COPY services/llm/pyproject.toml services/llm/poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi
COPY services/llm/ .
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

# ============================================================
FROM base AS graph
COPY services/graph/pyproject.toml services/graph/poetry.lock ./
RUN poetry lock --no-cache && poetry install --only main --no-interaction --no-ansi
COPY services/graph/ .
EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

# ============================================================
FROM base AS agent
COPY services/agent/pyproject.toml services/agent/poetry.lock ./
RUN poetry lock --no-cache && poetry install --only main --no-interaction --no-ansi
COPY services/agent/ .
EXPOSE 8004
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
