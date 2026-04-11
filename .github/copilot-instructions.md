# OasisAI repository instructions

## Build, test, and lint

Use the repo root `Makefile` and root Poetry environment for day-to-day work.

```bash
make setup
make install
make format
make format-check
make lint
make test-unit
make test-integration
make test-coverage
make docker build
make docker up
make check-health
```

Run a single test directly with `pytest` from the repo root:

```bash
poetry run pytest tests/unit/test_gateway.py::TestGatewayAsk::test_ask_forwards_to_agent -v
poetry run pytest tests/integration/test_integration.py::TestGatewayHealth::test_health_check -vv
```

Run individual services without Docker:

```bash
make run gateway
make run indexer
make run agent
make run graph
make run llm
```

For the local stack and the integration suite, the gateway is exposed on `http://localhost:8080`. Some older docs still mention `:8000`.

## High-level architecture

OasisAI is a small service mesh built from five FastAPI apps under `services/` plus ChromaDB and Ollama:

- `gateway` is the public API surface for `/ask`, `/search`, `/refactor`, and `/index`.
- `llm` wraps Ollama for `/generate`, `/embed`, and `/embed_batch`.
- `indexer` scans repositories, chunks code, requests embeddings, and upserts vectors into Chroma.
- `graph` parses Python files with the stdlib `ast` module and returns dependency graph nodes/edges.
- `agent` orchestrates ask/refactor flows by retrieving semantic context and optionally expanding dependency context.

The important request flow is split across services:

- `/search` goes through `gateway`, embeds the query via `llm`, then queries Chroma directly.
- `/ask` and `/refactor` go through `gateway` to `agent`; `agent` retrieves context, optionally calls `graph`, then calls `llm`.
- `/index` goes through `gateway` to `indexer`; `indexer` scans `/repos`, chunks files into overlapping line windows, embeds batches, and writes to the Chroma collection `oasis_code`.

`shared/` holds cross-service infrastructure: environment-backed settings, shared Pydantic models, JSON logging with request IDs, retry helpers, and the in-memory TTL cache. `storage/chroma/client.py` is the reusable Chroma wrapper, even though `gateway` and `indexer` also talk to Chroma directly in their own modules.

## Key conventions

- Keep repo-wide tooling at the root. Even though each service has its own directory and some have their own `pyproject.toml`, the authoritative developer commands are the root `Makefile` and root Poetry environment.
- `shared/schemas/models.py` is the shared contract layer, but several services also define FastAPI request/response models locally in `main.py`. When changing API payloads, update both the shared models and the service-local models/tests that validate them.
- Preserve the logging pattern from `shared/observability/logging.py`: services call `configure_logging(...)`, install `request_logging_middleware`, and propagate `x-request-id` through logs and responses.
- Treat `shared.config.settings` as the central config surface. Default service URLs are Docker-oriented (`http://llm:8001`, `http://agent:8004`, etc.), so running services outside Compose usually requires env overrides.
- The indexer is incremental. It stores per-file hashes in `.oasis_index_state.json`, skips unchanged files, and uses deterministic chunk IDs derived from `repo + file_path + chunk_index`.
- Preserve Chroma metadata shape when editing indexing/search behavior: `repo`, `file_path`, `language`, `start_line`, `end_line`, and `chunk_index`.
- The repo scanner supports multiple languages, but graph expansion is Python-only. Do not expect non-Python files to produce graph nodes or dependency edges.
- Refactor output is read-only by design: `agent` returns a text plan plus unified diff strings and does not modify repository files.
- Prefer current code, `Makefile`, and `compose/docker-compose.yml` over prose docs when they disagree. There is known drift in gateway port references and model defaults between docs, settings, and compose.
