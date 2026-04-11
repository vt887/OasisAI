"""oasis-ai graph FastAPI service."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from graph_builder import GraphBuilder
from parser import PythonASTParser
from pydantic import BaseModel

from shared.graph import cross_repo

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


@app.post("/graph/persist", response_model=GraphResponse)
def build_and_persist_graph(req: GraphRequest) -> GraphResponse:
    """Build the graph from files and persist it to the shared graph store."""
    try:
        parser = PythonASTParser()
        parsed = []
        for p in req.file_paths:
            mod = parser.parse_file(p, repo=req.repo)
            if mod:
                parsed.append(mod)
        cross_repo.build_from_parsed_modules(parsed)
        # Return persisted view
        store = cross_repo._load_store()
        nodes = list(store.get("nodes", {}).values())
        edges = store.get("edges", [])
        return GraphResponse(nodes=nodes, edges=edges, repo=req.repo)
    except Exception as exc:
        logger.exception("Graph persist failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
