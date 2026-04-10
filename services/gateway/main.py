"""oasis-ai gateway: main API gateway orchestrating all OasisAI services."""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
import httpx
from chromadb.config import Settings
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-gateway")

INDEXER_URL = os.getenv("INDEXER_URL", "http://indexer:8002")
AGENT_URL = os.getenv("AGENT_URL", "http://agent:8004")
GRAPH_URL = os.getenv("GRAPH_URL", "http://graph:8003")
LLM_URL = os.getenv("LLM_URL", "http://llm:8001")
CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

app = FastAPI(
    title="OasisAI Gateway",
    version="0.1.0",
    description="AI-powered code intelligence platform",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_http = httpx.Client(timeout=180.0)
_chroma = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
    settings=Settings(anonymized_telemetry=False),
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class SearchResponse(BaseModel):
    results: list[dict[str, Any]] = []


class RefactorRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    repo: str | None = None
    target_file: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class RefactorResponse(BaseModel):
    plan: str
    patches: list[str] = []
    sources: list[dict[str, Any]] = []


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
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail=f"Upstream unavailable: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
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
    try:
        # Embed the query via LLM service
        embed_resp = _forward(
            f"{LLM_URL}/embed",
            {"text": req.query},
        )
        query_embedding = embed_resp.get("embedding", [])

        # Query ChromaDB directly
        collection = _chroma.get_or_create_collection(
            name="oasis_code",
            metadata={"hnsw:space": "cosine"},
        )

        where: dict[str, Any] | None = None
        if req.repo:
            where = {"repo": req.repo}

        from typing import cast

        # ChromaDB typing expects IncludeEnum entries; cast the string list
        include_param = cast(Any, ["documents", "metadatas", "distances"])

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=req.top_k,
            where=where,
            include=include_param,
        )

        # Format results
        hits: list[dict[str, Any]] = []
        # results values can be None; ensure we have indexable lists
        ids_all = results.get("ids") or [[]]
        docs_all = results.get("documents") or [[]]
        metas_all = results.get("metadatas") or [[]]
        dists_all = results.get("distances") or [[]]

        ids = ids_all[0]
        docs = docs_all[0]
        metas = metas_all[0]
        dists = dists_all[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "content": doc,
                    "metadata": meta,
                    "distance": float(dist),
                }
            )
        return SearchResponse(results=hits)
    except Exception as exc:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
