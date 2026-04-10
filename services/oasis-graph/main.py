"""oasis-graph FastAPI service."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from graph_builder import GraphBuilder

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-graph")

app = FastAPI(title="oasis-graph", version="0.1.0")
builder = GraphBuilder()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GraphRequest(BaseModel):
    file_paths: list[str]
    repo: str = ""


class GraphResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    repo: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "oasis-graph"}


@app.post("/graph", response_model=GraphResponse)
def build_graph(req: GraphRequest) -> GraphResponse:
    """Parse Python files and return the dependency graph."""
    try:
        graph = builder.build_from_files(req.file_paths, repo=req.repo)
        data = graph.to_dict()
        return GraphResponse(nodes=data["nodes"], edges=data["edges"], repo=req.repo)
    except Exception as exc:
        logger.exception("Graph build failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
