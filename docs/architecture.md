# OasisAI — Architecture

## Overview

OasisAI is a production-ready, self-hosted AI code intelligence platform for
multi-repository systems. It combines semantic code search (via embeddings)
with structural code understanding (via AST graphs) and an LLM reasoning layer
to power Copilot-like assistants, automated refactoring, and codebase Q&A.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Developer / IDE                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │  REST (JSON)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      oasis-gateway  :8000                       │
│  POST /ask   POST /search   POST /refactor   POST /index        │
└───────┬──────────────────────────────────────────┬─────────────┘
        │                                          │
        ▼                                          ▼
┌───────────────┐                      ┌───────────────────────┐
│  oasis-agent  │                      │   oasis-indexer       │
│  :8004        │                      │   :8002               │
│               │                      │                       │
│  ask()        │                      │  scan repo            │
│  refactor()   │                      │  chunk code           │
└───────┬───────┘                      │  embed via oasis-llm  │
        │                              │  store in chroma      │
        ├─────────────────────┐        └──────────┬────────────┘
        │                     │                   │
        ▼                     ▼                   ▼
┌──────────────┐   ┌─────────────────┐  ┌─────────────────────┐
│  oasis-llm   │   │  oasis-graph    │  │     ChromaDB        │
│  :8001       │   │  :8003          │  │     :8010           │
│              │   │                 │  │                     │
│  generate()  │   │  AST parsing    │  │  vector storage     │
│  embed()     │   │  graph build    │  │  semantic search    │
└──────┬───────┘   └─────────────────┘  └─────────────────────┘
       │
       ▼
┌─────────────┐
│   Ollama    │
│   :11434    │
│             │
│  codellama  │
│  nomic-     │
│  embed-text │
└─────────────┘
```

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| `oasis-gateway` | 8000 | Public REST API; orchestrates all services |
| `oasis-llm` | 8001 | Ollama wrapper for generation and embeddings |
| `oasis-indexer` | 8002 | Scans repos, chunks code, stores in ChromaDB |
| `oasis-graph` | 8003 | AST parser; builds function/class dependency graph |
| `oasis-agent` | 8004 | Retrieves context; generates refactor plans + diffs |
| `ChromaDB` | 8010 | Vector store for code embeddings |
| `Ollama` | 11434 | Local LLM server (`codellama`, `nomic-embed-text`) |

---

## Data Flow

### Ingestion (indexing a repository)

```
POST /index  →  oasis-gateway
                    → oasis-indexer
                        → scan /repos/<name>  (filesystem)
                        → split into line-window chunks
                        → POST /embed  → oasis-llm → Ollama
                        → POST /upsert → ChromaDB
```

### Semantic Search

```
POST /search  →  oasis-gateway
                    → POST /embed  → oasis-llm → Ollama
                    → POST /query  → ChromaDB
                    ← ranked results (content + metadata)
```

### Ask (Q&A)

```
POST /ask  →  oasis-gateway
                → oasis-agent
                    → POST /search  (semantic context retrieval)
                    → build prompt
                    → POST /generate  → oasis-llm → Ollama
                    ← answer + source chunks
```

### Refactor

```
POST /refactor  →  oasis-gateway
                    → oasis-agent
                        → POST /search   (semantic context)
                        → POST /graph    → oasis-graph  (dependency expansion)
                        → build prompt
                        → POST /generate → oasis-llm → Ollama
                        ← plan + unified-diff patches (files NOT modified)
```

---

## Key Design Decisions

1. **Stateless services** — each service is a pure HTTP worker; no shared in-process state.
2. **Shared schemas in `/shared/schemas`** — single source of truth for all Pydantic models.
3. **ChromaDB as the vector store** — cosine-similarity search over code embeddings, with per-repo metadata filtering.
4. **Ollama for zero-cloud-dependency LLMs** — works fully offline with `codellama` (generation) and `nomic-embed-text` (embeddings).
5. **Read-only refactoring** — the agent produces unified diffs but never modifies files directly.
6. **AST-only graph** — the graph service uses Python's stdlib `ast` module; no third-party parsers required for Python.

---

## Directory Structure

```
OasisAI/
├── services/
│   ├── oasis-gateway/   FastAPI public API  (port 8000)
│   ├── oasis-llm/       Ollama wrapper      (port 8001)
│   ├── oasis-indexer/   Ingestion pipeline  (port 8002)
│   ├── oasis-graph/     AST code graph      (port 8003)
│   └── oasis-agent/     Reasoning engine    (port 8004)
├── storage/
│   └── chroma/          ChromaDB client wrapper
├── shared/
│   └── schemas/         Pydantic models (shared contracts)
├── docker/
│   └── docker-compose.yml
├── docs/
│   └── architecture.md  (this file)
└── repos/               Mount point for repositories to index
```

---

## Getting Started

### Prerequisites

- Docker + Docker Compose
- At least 8 GB RAM (for LLM models)

### 1. Pull required Ollama models

```bash
# Start Ollama first
docker compose -f docker/docker-compose.yml up ollama -d

# Pull models
docker exec -it <ollama_container> ollama pull codellama
docker exec -it <ollama_container> ollama pull nomic-embed-text
```

### 2. Start the full stack

```bash
docker compose -f docker/docker-compose.yml up --build
```

### 3. Index a repository

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/repos/myproject", "repo_name": "myproject"}'
```

### 4. Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How does authentication work?", "repo": "myproject"}'
```

### 5. Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection pooling", "top_k": 5}'
```

### 6. Refactor

```bash
curl -X POST http://localhost:8000/refactor \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Extract the DB logic into a separate module", "repo": "myproject"}'
```

---

## API Reference

### `POST /ask`
| Field | Type | Description |
|---|---|---|
| `question` | string | Natural language question |
| `repo` | string? | Limit context to this repo |
| `top_k` | int | Number of chunks to retrieve (default: 5) |

### `POST /search`
| Field | Type | Description |
|---|---|---|
| `query` | string | Semantic search query |
| `repo` | string? | Limit to this repo |
| `top_k` | int | Max results (default: 5) |

### `POST /refactor`
| Field | Type | Description |
|---|---|---|
| `instruction` | string | Natural language refactor goal |
| `repo` | string? | Target repo |
| `target_file` | string? | Specific file for graph expansion |
| `top_k` | int | Context chunks (default: 5) |

### `POST /index`
| Field | Type | Description |
|---|---|---|
| `repo_path` | string | Absolute path to the git repo |
| `repo_name` | string | Logical name for the repo |
