# ============================================================
# OasisAI — Multistage root Dockerfile (OPTIMIZED FOR SHARED DEPS)
# Build any service with: docker build --target <service> .
# Used by compose/docker-compose.yml via `context: ..`
# ============================================================
ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=2.2.1

# ============================================================
# Deps stage — install Poetry only, leave package installation
# to per-service stages so images only contain required deps.
# ============================================================
FROM python:${PYTHON_VERSION}-slim AS deps
ARG POETRY_VERSION
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pypoetry \
    pip install --no-cache-dir "poetry==${POETRY_VERSION}" && \
    poetry config virtualenvs.create false


# ============================================================
# Base stage — reuse deps stage so installed console scripts
# and site-packages remain available in runtime images.
# ============================================================
FROM deps AS base
COPY shared/ ./shared/
COPY storage/ ./storage/

# ============================================================
# Dev / test image
# ============================================================
FROM deps AS development
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --with dev --no-interaction --no-ansi
COPY . .
CMD ["python", "-m", "pytest", "tests/unit/"]

# ============================================================
# Gateway service
# ============================================================
FROM deps AS gateway
WORKDIR /app
COPY services/gateway/pyproject.toml services/gateway/poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi
COPY services/gateway/ .
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

# ============================================================
# Indexer service
# ============================================================
FROM deps AS indexer
WORKDIR /app
COPY services/indexer/pyproject.toml services/indexer/poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi
COPY services/indexer/ .
VOLUME ["/repos"]
EXPOSE 8002
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

# ============================================================
# LLM service
# ============================================================
FROM deps AS llm
WORKDIR /app
COPY services/llm/pyproject.toml services/llm/poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi
COPY services/llm/ .
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

# ============================================================
# Graph service
# ============================================================
FROM deps AS graph
WORKDIR /app
COPY services/graph/pyproject.toml services/graph/poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi
COPY services/graph/ .
EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

# ============================================================
# Agent service
# ============================================================
FROM deps AS agent
WORKDIR /app
COPY services/agent/pyproject.toml services/agent/poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi
COPY services/agent/ .
EXPOSE 8004
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
