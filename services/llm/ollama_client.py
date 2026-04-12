from __future__ import annotations

import hashlib
from typing import Any

import httpx

from shared.cache import TTLCache
from shared.config import settings
from shared.resilience import async_retry


class OllamaClient:
    def __init__(
        self,
        base_url: str = settings.ollama_url,
        default_model: str = settings.default_model,
        embed_model: str = settings.embed_model,
        timeout: float = settings.request_timeout_seconds,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._default_model = default_model
        self._embed_model = embed_model
        self._client = httpx.AsyncClient(timeout=timeout)
        self._embed_cache = TTLCache[str, list[float]](
            max_size=settings.embed_cache_size,
            ttl_seconds=settings.cache_ttl_seconds,
        )

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        async def _call() -> str:
            response = await self._client.post(
                f"{self._base}/api/generate", json=payload
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", ""))

        return await async_retry(
            _call,
            retries=settings.retries,
            backoff_seconds=settings.backoff_seconds,
        )

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        mdl = model or self._embed_model
        cache_key = hashlib.sha256(f"{mdl}:{text}".encode()).hexdigest()
        if settings.cache_enabled:
            cached = self._embed_cache.get(cache_key)
            if cached is not None:
                return cached

        payload = {"model": mdl, "input": text}

        async def _call() -> list[float]:
            response = await self._client.post(
                f"{self._base}/api/embed", json=payload
            )
            response.raise_for_status()
            data = response.json()
            embeddings = (
                data.get("embeddings") if isinstance(data, dict) else []
            )
            if isinstance(embeddings, list) and embeddings:
                first = embeddings[0]
                if isinstance(first, list):
                    return [float(value) for value in first]
            embedding = data.get("embedding") if isinstance(data, dict) else []
            return (
                [float(value) for value in embedding]
                if isinstance(embedding, list)
                else []
            )

        result = await async_retry(
            _call,
            retries=settings.retries,
            backoff_seconds=settings.backoff_seconds,
        )
        if settings.cache_enabled:
            self._embed_cache.set(cache_key, result)
        return result

    async def embed_batch(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        import asyncio

        return await asyncio.gather(
            *[self.embed(t, model=model) for t in texts]
        )

    async def close(self) -> None:
        await self._client.aclose()
