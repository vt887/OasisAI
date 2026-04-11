from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from ollama_client import OllamaClient
from pydantic import BaseModel

from shared.config import settings
from shared.observability.logging import (
    configure_logging,
    request_logging_middleware,
)
from shared.timing import calculate_duration_ms

logger = configure_logging("oasis-llm", settings.log_level)

app = FastAPI(title="OasisAI LLM", version="0.2.0")
client = OllamaClient(
    base_url=settings.ollama_url,
    default_model=settings.default_model,
    embed_model=settings.embed_model,
    timeout=settings.request_timeout_seconds,
)


@app.middleware("http")
async def log_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Any]]
) -> Any:
    return await request_logging_middleware(request, call_next, logger)


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("global error", extra={"operation": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Unexpected server error",
        },
    )


class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = None
    system: str | None = None
    options: dict[str, Any] = {}


class GenerateResponse(BaseModel):
    text: str
    model: str


class EmbedRequest(BaseModel):
    text: str
    model: str | None = None


class EmbedBatchRequest(BaseModel):
    texts: list[str]
    model: str | None = None


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str


class EmbedBatchResponse(BaseModel):
    embeddings: list[list[float]]
    model: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-llm"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    model = req.model or settings.default_model
    start = time.perf_counter()
    try:
        text = await client.generate(
            prompt=req.prompt,
            model=model,
            system=req.system,
            options=req.options or None,
        )
        logger.info(
            "generate complete",
            extra={
                "operation": "generate",
                "duration_ms": calculate_duration_ms(start),
            },
        )
        return GenerateResponse(text=text, model=model)
    except Exception as exc:
        logger.exception("generate failed", extra={"operation": "generate"})
        raise HTTPException(
            status_code=502, detail="LLM generation failed"
        ) from exc


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    model = req.model or settings.embed_model
    start = time.perf_counter()
    try:
        vector = await client.embed(text=req.text, model=model)
        logger.info(
            "embed complete",
            extra={
                "operation": "embed",
                "duration_ms": calculate_duration_ms(start),
            },
        )
        return EmbedResponse(embedding=vector, model=model)
    except Exception as exc:
        logger.exception("embed failed", extra={"operation": "embed"})
        raise HTTPException(
            status_code=502, detail="Embedding generation failed"
        ) from exc


@app.post("/embed_batch", response_model=EmbedBatchResponse)
async def embed_batch(req: EmbedBatchRequest) -> EmbedBatchResponse:
    model = req.model or settings.embed_model
    try:
        embeddings = [
            await client.embed(text=t, model=model) for t in req.texts
        ]
        return EmbedBatchResponse(embeddings=embeddings, model=model)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Batch embedding failed"
        ) from exc
