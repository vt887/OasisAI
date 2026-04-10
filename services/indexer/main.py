"""oasis-ai indexer FastAPI service."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from pipeline import IndexPipeline
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-indexer")

REPOS_ROOT = os.getenv("REPOS_ROOT", "/repos")

app = FastAPI(
    title="OasisAI Indexer",
    version="0.1.0",
    description="AI-powered code intelligence platform",
)

pipeline = IndexPipeline()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IndexRequest(BaseModel):
    repo_path: str
    repo_name: str


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int
    status: str = "ok"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-indexer"}


@app.post("/index", response_model=IndexResponse)
def index_repo(req: IndexRequest) -> IndexResponse:
    """Ingest and embed a repository into ChromaDB."""
    try:
        count = pipeline.index_repo(
            repo_path=req.repo_path,
            repo_name=req.repo_name,
        )
        return IndexResponse(repo_name=req.repo_name, chunks_indexed=count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Indexing failed for repo=%s", req.repo_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
