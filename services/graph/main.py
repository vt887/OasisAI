"""oasis-ai graph FastAPI service."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from graph_builder import GraphBuilder
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-graph")

app = FastAPI(
    title="OasisAI Graph",
    version="0.1.0",
    description="AI-powered code intelligence platform",
)
builder = GraphBuilder()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GraphRequest(BaseModel):
    file_paths: list[str]
    repo: str = ""


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    repo: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-graph"}


@app.post("/graph", response_model=GraphResponse)
def build_graph(req: GraphRequest) -> GraphResponse:
    """Parse Python files and return the dependency graph."""
    try:
        graph = builder.build_from_files(req.file_paths, repo=req.repo)
        data = graph.to_dict()
        return GraphResponse(
            nodes=data["nodes"], edges=data["edges"], repo=req.repo
        )
    except Exception as exc:
        logger.exception("Graph build failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
