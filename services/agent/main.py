"""oasis-ai agent FastAPI service."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent import RefactorAgent

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-agent")

app = FastAPI(title="oasis-agent", version="0.1.0")
agent = RefactorAgent()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str
    repo: str | None = None
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = []


class RefactorRequest(BaseModel):
    instruction: str
    repo: str | None = None
    target_file: str | None = None
    top_k: int = 5


class RefactorResponse(BaseModel):
    plan: str
    patches: list[str] = []
    sources: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-agent"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        result = agent.ask(
            question=req.question, repo=req.repo, top_k=req.top_k
        )
        return AskResponse(**result)
    except Exception as exc:
        logger.exception("ask failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/refactor", response_model=RefactorResponse)
def refactor(req: RefactorRequest) -> RefactorResponse:
    try:
        result = agent.refactor(
            instruction=req.instruction,
            repo=req.repo,
            target_file=req.target_file,
            top_k=req.top_k,
        )
        return RefactorResponse(**result)
    except Exception as exc:
        logger.exception("refactor failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
