# OasisAI

AI-powered code intelligence platform for multi-repository systems.

OasisAI ingests git repositories, builds a semantic index, analyzes code
structure with an AST graph, and provides natural-language question
answering and refactor plan generation — all runnable locally.

Contents
- Quick Start
- Requirements
- Kubernetes (Helm) deployment
- Environment variables
- Troubleshooting
- Documentation links

---

## Quick Start

There are two main ways to run the system locally: the provided startup
script (convenient) or Docker Compose (more explicit). Both approaches
assume Docker is available on your machine.

1) Start with the startup script

```bash
chmod +x start.sh
./start.sh
```

2) Or start manually with Docker Compose

```bash
docker compose -f docker/docker-compose.yml up --build
```

3) Validate the running system

```bash
python validate.py
```

Core HTTP endpoints (gateway, default port 8000):

- POST /index   → start repo indexing
- POST /search  → semantic search
- POST /ask     → question answering
- POST /refactor→ generate refactor plan + patches

Example: index a repository

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/repos/myproject", "repo_name": "myproject"}'
```

---

## Requirements

System prerequisites

- Docker (Engine and Compose)
- Helm (for optional K8s deployment)
- kubectl (to interact with clusters)
- A Kubernetes cluster for Helm installs (kind, minikube, k3s, GKE, etc.)

Python & tooling

- Python 3.10+ (poetry uses the project's pyproject)
- Poetry (dependency and virtualenv management)

LLM / embeddings

- Ollama: required for the local LLM and embedding endpoints. Install
  Ollama on the host or run the provided Ollama container in Docker.
  Pull recommended models:

```bash
# on the Ollama host/container
ollama pull codellama
ollama pull nomic-embed-text
```

Optional services

- ChromaDB (vector store) — the indexer stores embeddings here. The
  Docker Compose stack includes a Chroma instance used for development.

---

## Kubernetes (Helm) deployment

The `helm/` chart can deploy OasisAI to a cluster. The chart is suited
for development clusters (kind, minikube). For production you must tune
resources, storage classes, and ingress settings in `helm/values.yaml`.

Prerequisites

- A running Kubernetes cluster and `kubectl` configured
- `helm` 3.x installed
- A registry reachable from the cluster for the project images (or use
  images built and pushed by your CI)

Install the chart (example)

```bash
# Lint the chart
helm lint helm

# Render templates to inspect output
helm template oasisai helm -f helm/values.yaml

# Install into namespace "oasisai"
helm install oasisai helm --namespace oasisai --create-namespace \
  -f helm/values.yaml --wait

# Upgrade
helm upgrade oasisai helm --namespace oasisai -f helm/values.yaml --wait

# Uninstall
helm uninstall oasisai --namespace oasisai

# Run chart tests (if present)
helm test oasisai --namespace oasisai
```

Notes

- Override image tags and storage via `-f` or `--set` when calling
  `helm install` / `helm upgrade`.
- The chart includes `helm/tests/` manifests which can be used with
  `helm test` to validate basic connectivity after deploy.

---

## Environment variables

Key environment variables used by services (can be set in compose or
Helm values):

- OLLAMA_URL — Ollama HTTP endpoint (default: http://ollama:11434)
- LLM_MODEL — default model for generations (e.g. codellama)
- EMBED_MODEL — embedding model (e.g. nomic-embed-text)
- CHROMA_HOST / CHROMA_PORT — ChromaDB host and port
- GRAPH_URL — oasis-graph service URL
- LLM_URL — oasis-llm service URL

Set these in `docker/docker-compose.yml` or via your Helm values file.

---

## Troubleshooting

- Services won't start?
  - Ensure Docker is running: `docker --version`
  - Check ports: `lsof -i :8000 8001 8002 8003 8004`
  - View logs: `docker compose -f docker/docker-compose.yml logs`

- Ollama models not found
  - Pull models into your Ollama instance: see Requirements section.

- Search returns no results
  - Ensure the repository completed indexing.
  - Check ChromaDB collections: `curl http://localhost:8000/api/v1/collections`

- Connection refused
  - Services may still be starting. Check health endpoints:
    - `curl http://localhost:8000/health`
    - `curl http://localhost:8001/health`

---

## Documentation

See the `docs/` directory for full guides and references. Key files:

- `docs/architecture.md` — architecture and component interactions
- `docs/QUICK_START.md` — short quick-start steps
- `docs/DEVELOPMENT.md` — developer-run instructions
- `docs/HELM_TESTS.md` — guidance on Helm chart tests
- `docs/START_HERE.md` — onboarding order for new contributors

For a complete list, inspect the `docs/` directory in the repo.

---

## Testing

The test suite is organized into unit and integration tests:

```bash
# Run all unit tests (fast, no external services required)
make test-unit

# Run all integration tests (requires running services)
make test-integration
```

Unit test coverage:

- `tests/unit/test_gateway.py` — gateway endpoint mocking and validation
- `tests/unit/test_indexer.py` — indexer pipeline, chunking, scanning
- `tests/unit/test_graph.py` — AST parser and graph builder
- `tests/unit/test_schemas.py` — Pydantic model validation

Integration tests:

- `tests/integration/test_integration.py` — end-to-end API tests against
  running service stack

---

## Repository structure (overview)

```
oasis-ai/
├── services/           # gateway, llm, indexer, graph, agent
├── storage/            # ChromaDB client wrapper
├── shared/             # shared pydantic schemas
├── tests/
│   ├── unit/           # unit tests (fast, no service dependencies)
│   └── integration/    # integration tests (full service stack)
├── compose/            # docker-compose for local dev
├── helm/               # Helm chart for Kubernetes
├── docs/               # project documentation
└── repos/              # mount point for repositories to index
```

---

## Tech stack

- API framework: FastAPI
- Vector store: ChromaDB
- LLM / Embeddings: Ollama (codellama, nomic-embed-text)
- Schemas: Pydantic v2
- Dependency management: Poetry
- Local deployment: Docker Compose; optional K8s via Helm
