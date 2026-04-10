"""Indexing pipeline: scan, chunk, embed, and store into ChromaDB."""

from __future__ import annotations

import logging
import os
from typing import Any, cast

import chromadb
import httpx
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings
from chunker import CodeChunker
from scanner import RepoScanner

logger = logging.getLogger(__name__)

_BATCH_SIZE = 32  # chunks per embedding/upsert batch

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
LLM_URL = os.getenv("LLM_URL", "http://llm:8001")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


class IndexPipeline:
    """End-to-end pipeline: scan → chunk → embed → store in ChromaDB."""

    def __init__(
        self,
        chroma_host: str = CHROMA_HOST,
        chroma_port: int = CHROMA_PORT,
        llm_url: str = LLM_URL,
        embed_model: str = EMBED_MODEL,
    ) -> None:
        self._chroma_host = chroma_host
        self._chroma_port = chroma_port
        self._llm_url = llm_url.rstrip("/")
        self._embed_model = embed_model
        self._chunker = CodeChunker()
        # Delay network/service clients until actually needed so import
        # time does not attempt network calls (which can fail during
        # process startup). They will be created lazily by
        # ``_ensure_initialized``.
        self._http: httpx.Client | None = None
        self._chroma: ClientAPI | None = None
        self._collection: Collection | None = None
        self._initialized = False

        logger.info(
            "IndexPipeline created (deferred init): chroma=%s:%d, llm=%s",
            chroma_host,
            chroma_port,
            llm_url,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_repo(self, repo_path: str, repo_name: str) -> int:
        """Scan, chunk, embed and store an entire repository.

        Returns the number of chunks indexed.
        """
        # Ensure network clients are available before performing work.
        self._ensure_initialized()

        scanner = RepoScanner(repo_path)
        files = scanner.scan()

        all_chunks: list[dict[str, Any]] = []
        for file_path, language in files:
            chunks = self._chunker.chunk_file(
                file_path=file_path,
                repo=repo_name,
                language=language,
            )
            all_chunks.extend(chunks)

        logger.info(
            "repo=%s: %d total chunks to index", repo_name, len(all_chunks)
        )

        indexed = 0
        for batch_start in range(0, len(all_chunks), _BATCH_SIZE):
            batch = all_chunks[batch_start : batch_start + _BATCH_SIZE]
            embeddings = self._embed_batch([c["content"] for c in batch])
            self._upsert_batch(batch, embeddings)
            indexed += len(batch)
            logger.info(
                "repo=%s: indexed %d/%d chunks",
                repo_name,
                indexed,
                len(all_chunks),
            )

        return indexed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        # HTTP client required to call the embedding endpoint.
        self._ensure_initialized()
        if self._http is None:
            raise RuntimeError("HTTP client is not available")
        embeddings: list[list[float]] = []
        for text in texts:
            resp = self._http.post(
                f"{self._llm_url}/embed",
                json={"text": text, "model": self._embed_model},
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
        return embeddings

    def _upsert_batch(
        self, chunks: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
        """Upsert chunks directly to ChromaDB collection."""
        # If Chroma isn't available, raise a runtime error instead
        # of failing quietly; callers may catch this and decide to
        # retry or abort.
        self._ensure_initialized()
        if self._collection is None:
            raise RuntimeError("ChromaDB collection is not available")

        self._collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=cast(Any, embeddings),
            documents=[c["content"] for c in chunks],
            metadatas=[
                {
                    "repo": c["repo"],
                    "file_path": c["file_path"],
                    "language": c["language"],
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                    "chunk_index": c["chunk_index"],
                }
                for c in chunks
            ],
        )

    def close(self) -> None:
        if self._http is not None:
            self._http.close()

    def _ensure_initialized(self) -> None:
        """Create network clients and the Chroma collection lazily.

        This avoids performing network I/O during module import which
        can cause problems when the process is started in a child
        process (e.g. by uvicorn's subprocess mode).
        """
        if self._initialized:
            return

        # Always create an HTTP client for LLM calls.
        if self._http is None:
            self._http = httpx.Client(timeout=120.0)

        try:
            # Chroma is optional during development; log and continue if
            # it cannot be reached.
            self._chroma = chromadb.HttpClient(
                host=self._chroma_host,
                port=self._chroma_port,
                settings=Settings(anonymized_telemetry=False),
            )
            if self._chroma is not None:
                self._collection = self._chroma.get_or_create_collection(
                    name="oasis_code", metadata={"hnsw:space": "cosine"}
                )
        except Exception as exc:  # pragma: no cover - external service
            logger.warning("Failed to initialize ChromaDB client: %s", exc)
            self._chroma = None
            self._collection = None

        self._initialized = True
