"""oasis-llm FastAPI service — exposes LLM generate and embed endpoints."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException

from ollama_client import OllamaClient

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis-llm")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "codellama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

app = FastAPI(title="oasis-llm", version="0.1.0")
client = OllamaClient(
    base_url=OLLAMA_URL,
    default_model=DEFAULT_MODEL,
    embed_model=EMBED_MODEL,
)

# ---------------------------------------------------------------------------
# Request / Response models (inline for service independence)
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from typing import Any


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


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "oasis-llm"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        model = req.model or DEFAULT_MODEL
        text = client.generate(
            prompt=req.prompt,
            model=model,
            system=req.system,
            options=req.options or None,
        )
        return GenerateResponse(text=text, model=model)
    except Exception as exc:
        logger.exception("generate failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    try:
        model = req.model or EMBED_MODEL
        vector = client.embed(text=req.text, model=model)
        return EmbedResponse(embedding=vector, model=model)
    except Exception as exc:
        logger.exception("embed failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
