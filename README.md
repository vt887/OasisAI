# OasisAI

**AI-powered code intelligence platform for multi-repository systems.**

OasisAI lets you ingest entire git repositories, search them semantically,
ask questions in natural language, and generate refactor plans — all running
locally, without cloud dependencies.

---

## Quick Start

```bash
# 1. Start the full stack (ChromaDB + Ollama + all services)
docker compose -f docker/docker-compose.yml up --build

# 2. Pull required Ollama models (first time only)
docker exec -it oasisai-ollama-1 ollama pull codellama
docker exec -it oasisai-ollama-1 ollama pull nomic-embed-text

# 3. Index a repository
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/repos/myproject", "repo_name": "myproject"}'

# 4. Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How does authentication work?", "repo": "myproject"}'

# 5. Semantic search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection pooling"}'

# 6. Refactor
curl -X POST http://localhost:8000/refactor \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Extract DB logic into a separate module", "repo": "myproject"}'
```

---

## Architecture

```
Developer → oasis-gateway → oasis-agent → oasis-llm → Ollama
                          ↘ oasis-indexer → ChromaDB
                          ↘ oasis-graph  (AST analysis)
```

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Repository Structure

```
OasisAI/
├── services/
│   ├── oasis-gateway/   Public REST API          (port 8000)
│   ├── oasis-llm/       Ollama wrapper           (port 8001)
│   ├── oasis-indexer/   Ingestion pipeline       (port 8002)
│   ├── oasis-graph/     AST code graph           (port 8003)
│   └── oasis-agent/     Reasoning engine         (port 8004)
├── storage/
│   └── chroma/          ChromaDB client wrapper
├── shared/
│   └── schemas/         Pydantic models (shared contracts)
├── docker/
│   └── docker-compose.yml
├── docs/
│   └── architecture.md
└── repos/               Mount point for repositories to index
```

---

## Tech Stack

| Component | Technology |
|---|---|
| API framework | FastAPI (Python 3.11+) |
| Vector store | ChromaDB |
| LLM / Embeddings | Ollama (`codellama`, `nomic-embed-text`) |
| Schemas | Pydantic v2 |
| Deployment | Docker Compose |
