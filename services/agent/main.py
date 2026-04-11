from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.observability.logging import (
    configure_logging,
    request_logging_middleware,
)

if TYPE_CHECKING:
    from .agent import RefactorAgent

_AGENT_MODULE: ModuleType = importlib.import_module(
    f"{__package__}.agent" if __package__ else "agent"
)

logger = configure_logging("oasis-agent")

app = FastAPI(title="oasis-agent", version="0.2.0")
agent: RefactorAgent = _AGENT_MODULE.RefactorAgent()


@app.middleware("http")
async def log_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Any]]
) -> Any:
    return await request_logging_middleware(request, call_next, logger)


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("agent unhandled", extra={"operation": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Unexpected server error",
        },
    )


class AskRequest(BaseModel):
    question: str
    repo: str | None = None
    top_k: int = 5
    debug: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = []


class RefactorRequest(BaseModel):
    instruction: str
    repo: str | None = None
    target_file: str | None = None
    top_k: int = 5
    debug: bool = False


class RefactorResponse(BaseModel):
    plan: str
    patches: list[str] = []
    sources: list[dict[str, Any]] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-agent"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    try:
        result = await agent.ask(
            question=req.question,
            repo=req.repo,
            top_k=req.top_k,
            debug=req.debug,
        )
        return AskResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="ask failed") from exc


@app.post("/refactor", response_model=RefactorResponse)
async def refactor(req: RefactorRequest) -> RefactorResponse:
    try:
        result = await agent.refactor(
            instruction=req.instruction,
            repo=req.repo,
            target_file=req.target_file,
            top_k=req.top_k,
            debug=req.debug,
        )
        return RefactorResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="refactor failed") from exc
