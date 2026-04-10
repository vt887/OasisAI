"""Ollama HTTP client wrapper.

Exposes two operations used by OasisAI services:
  - generate(prompt)   → text completion
  - embed(text)        → vector embedding
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"


class OllamaClient:
    """Typed wrapper around the Ollama REST API."""

    def __init__(
        self,
        base_url: str = _OLLAMA_BASE,
        default_model: str = "codellama",
        embed_model: str = "nomic-embed-text",
        timeout: float = 120.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._default_model = default_model
        self._embed_model = embed_model
        self._client = httpx.Client(timeout=timeout)

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> str:
        """Call /api/generate and return the response text."""
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        response = self._client.post(
            f"{self._base}/api/generate", json=payload
        )
        response.raise_for_status()
        data = response.json()
        text: str = data.get("response", "")
        logger.debug(
            "generate: model=%s, tokens=%d",
            payload["model"],
            len(text.split()),
        )
        return text

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Call /api/embeddings and return the embedding vector."""
        payload = {
            "model": model or self._embed_model,
            "prompt": text,
        }
        response = self._client.post(
            f"{self._base}/api/embeddings", json=payload
        )
        response.raise_for_status()
        data = response.json()
        embedding: list[float] = data.get("embedding", [])
        logger.debug(
            "embed: model=%s, dim=%d", payload["model"], len(embedding)
        )
        return embedding

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
