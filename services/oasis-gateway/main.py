"""oasis-gateway: main API gateway orchestrating all OasisAI services."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-gateway")

INDEXER_URL = os.getenv("INDEXER_URL", "http://oasis-indexer:8002")
AGENT_URL = os.getenv("AGENT_URL", "http://oasis-agent:8004")
GRAPH_URL = os.getenv("GRAPH_URL", "http://oasis-graph:8003")
LLM_URL = os.getenv("LLM_URL", "http://oasis-llm:8001")
CHROMA_URL = os.getenv("CHROMA_URL", "http://chroma:8000")

app = FastAPI(
    title="OasisAI Gateway",
    version="0.1.0",
    description="AI-powered code intelligence platform",
)

_http = httpx.Client(timeout=180.0)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class SearchResponse(BaseModel):
    results: list[dict] = []


class RefactorRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    repo: str | None = None
    target_file: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class RefactorResponse(BaseModel):
    plan: str
    patches: list[str] = []
    sources: list[dict] = []


class IndexRequest(BaseModel):
    repo_path: str
    repo_name: str


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int
    status: str = "ok"


# ---------------------------------------------------------------------------
# Helper: forward request to a downstream service
# ---------------------------------------------------------------------------

def _forward(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = _http.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Upstream unavailable: {exc}") from exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "oasis-gateway"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Ask a free-form question about the indexed codebase."""
    data = _forward(
        f"{AGENT_URL}/ask",
        {"question": req.question, "repo": req.repo, "top_k": req.top_k},
    )
    return AskResponse(**data)


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    """Semantic search across indexed code chunks."""
    # Embed the query via llm service, then query chroma
    embed_resp = _forward(
        f"{LLM_URL}/embed",
        {"text": req.query},
    )
    query_embedding = embed_resp.get("embedding", [])

    where: dict[str, Any] = {}
    if req.repo:
        where = {"repo": req.repo}

    chroma_resp = _forward(
        f"{CHROMA_URL}/query",
        {
            "query_embedding": query_embedding,
            "top_k": req.top_k,
            "where": where or None,
        },
    )
    results = chroma_resp.get("results", [])
    return SearchResponse(results=results)


@app.post("/refactor", response_model=RefactorResponse)
def refactor(req: RefactorRequest) -> RefactorResponse:
    """Generate a refactor plan and unified diff patches."""
    data = _forward(
        f"{AGENT_URL}/refactor",
        {
            "instruction": req.instruction,
            "repo": req.repo,
            "target_file": req.target_file,
            "top_k": req.top_k,
        },
    )
    return RefactorResponse(**data)


@app.post("/index", response_model=IndexResponse)
def index(req: IndexRequest) -> IndexResponse:
    """Trigger ingestion of a repository into ChromaDB."""
    data = _forward(
        f"{INDEXER_URL}/index",
        {"repo_path": req.repo_path, "repo_name": req.repo_name},
    )
    return IndexResponse(**data)
