from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import UUID

import chromadb
import httpx
from chromadb.config import Settings
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shared.cache import TTLCache
from shared.config import settings
from shared.observability.logging import (
    configure_logging,
    request_logging_middleware,
)
from shared.resilience import async_retry
from shared.timing import calculate_duration_ms

logger = configure_logging("oasis-gateway", settings.log_level)

app = FastAPI(title="OasisAI Gateway", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_http = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
_chroma = chromadb.HttpClient(
    host=settings.chroma_host,
    port=settings.chroma_port,
    settings=Settings(anonymized_telemetry=False),
)
_search_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
    max_size=512, ttl_seconds=settings.cache_ttl_seconds
)
_metrics: dict[str, float] = {"queries": 0, "query_latency_total_ms": 0}


def _get_chroma_collection_id() -> UUID:
    tenant = _chroma.tenant
    database = _chroma.database
    raw = cast(
        dict[str, Any],
        _chroma._server._make_request(  # type: ignore[attr-defined]
            "post",
            f"/tenants/{tenant}/databases/{database}/collections",
            json={
                "name": settings.chroma_collection,
                "metadata": {"hnsw:space": "cosine"},
                "configuration": None,
                "get_or_create": True,
            },
        ),
    )
    collection_id = raw.get("id")
    if not isinstance(collection_id, str):
        raise RuntimeError("Chroma collection response missing id")
    return UUID(collection_id)


def _query_chroma(
    query_embedding: list[float], top_k: int, repo: str | None
) -> dict[str, Any]:
    tenant = _chroma.tenant
    database = _chroma.database
    collection_id = _get_chroma_collection_id()
    include_param = cast(Any, ["documents", "metadatas", "distances"])
    return cast(
        dict[str, Any],
        _chroma._server._make_request(  # type: ignore[attr-defined]
            "post",
            f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/query",
            json={
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "where": {"repo": repo} if repo else None,
                "where_document": None,
                "include": include_param,
            },
        ),
    )


def _count_chroma_documents() -> int:
    tenant = _chroma.tenant
    database = _chroma.database
    collection_id = _get_chroma_collection_id()
    raw = _chroma._server._make_request(  # type: ignore[attr-defined]
        "get",
        f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/count",
    )
    return int(raw)


@app.middleware("http")
async def log_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Any]]
) -> Any:
    return await request_logging_middleware(request, call_next, logger)


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "gateway unhandled", extra={"operation": request.url.path}
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Unexpected server error",
        },
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)
    debug: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = []
    context_provenance: list[dict[str, Any]] | None = None


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
    debug: bool = False


class RefactorResponse(BaseModel):
    plan: str
    patches: list[str] = []
    sources: list[dict[str, Any]] = []
    affected_repos: list[str] | None = None
    impacted_symbols: list[str] | None = None


class IndexRequest(BaseModel):
    repo_path: str
    repo_name: str


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int
    status: str = "ok"


async def _forward(
    url: str, payload: dict[str, Any], operation: str
) -> dict[str, Any]:
    async def _call() -> dict[str, Any]:
        resp = await _http.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}

    try:
        return await async_retry(
            _call,
            retries=settings.retries,
            backoff_seconds=settings.backoff_seconds,
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504, detail=f"{operation} timeout"
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail=f"{operation} unavailable"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail="upstream error"
        ) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-gateway"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    checks = {"chroma": False, "ollama": False}
    try:
        _chroma.heartbeat()
        checks["chroma"] = True
    except Exception:
        checks["chroma"] = False
    try:
        resp = await _http.get(f"{settings.llm_url}/health")
        checks["ollama"] = resp.status_code == 200
    except Exception:
        checks["ollama"] = False
    return {
        "status": "ready" if all(checks.values()) else "degraded",
        "checks": checks,
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    avg = (
        0.0
        if _metrics["queries"] == 0
        else _metrics["query_latency_total_ms"] / _metrics["queries"]
    )
    docs = _count_chroma_documents()
    return {
        "indexed_documents": docs,
        "queries": int(_metrics["queries"]),
        "average_latency_ms": round(avg, 2),
    }


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    data = await _forward(
        f"{settings.agent_url}/ask",
        {
            "question": req.question,
            "repo": req.repo,
            "top_k": req.top_k,
            "debug": req.debug,
        },
        "ask",
    )
    return AskResponse(**data)


@app.get("/ask")
async def ask_help() -> dict[str, Any]:
    return {
        "message": "Use POST /ask with JSON body",
        "example": {
            "question": "How does authentication work?",
            "repo": "sample-app",
            "top_k": 5,
            "debug": False,
        },
    }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    start = time.perf_counter()
    key = f"{req.repo}:{req.top_k}:{req.query}"
    if settings.cache_enabled:
        cached = _search_cache.get(key)
        if cached is not None:
            return SearchResponse(results=cached)

    embed_resp = await _forward(
        f"{settings.llm_url}/embed", {"text": req.query}, "embed"
    )
    query_embedding = embed_resp.get("embedding", [])
    results = _query_chroma(
        cast(list[float], query_embedding), req.top_k, req.repo
    )

    hits: list[dict[str, Any]] = []
    for chunk_id, doc, meta, dist in zip(
        (results.get("ids") or [[]])[0],
        (results.get("documents") or [[]])[0],
        (results.get("metadatas") or [[]])[0],
        (results.get("distances") or [[]])[0],
    ):
        hits.append(
            {
                "id": chunk_id,
                "document": doc,
                "content": doc,
                "metadata": meta,
                "distance": float(dist),
            }
        )

    if settings.cache_enabled:
        _search_cache.set(key, hits)
    _metrics["queries"] += 1
    _metrics["query_latency_total_ms"] += calculate_duration_ms(start)

    return SearchResponse(results=hits)


@app.post("/refactor", response_model=RefactorResponse)
async def refactor(req: RefactorRequest) -> RefactorResponse:
    data = await _forward(
        f"{settings.agent_url}/refactor",
        {
            "instruction": req.instruction,
            "repo": req.repo,
            "target_file": req.target_file,
            "top_k": req.top_k,
            "debug": req.debug,
        },
        "refactor",
    )
    return RefactorResponse(**data)


@app.post("/index", response_model=IndexResponse)
async def index(req: IndexRequest) -> IndexResponse:
    data = await _forward(
        f"{settings.indexer_url}/index",
        {"repo_path": req.repo_path, "repo_name": req.repo_name},
        "index",
    )
    return IndexResponse(**data)
