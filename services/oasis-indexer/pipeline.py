"""Indexing pipeline: orchestrates scanning, chunking, embedding, and storage."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx

from scanner import RepoScanner
from chunker import CodeChunker

logger = logging.getLogger(__name__)

_BATCH_SIZE = 32   # chunks per embedding/upsert batch

CHROMA_URL = os.getenv("CHROMA_URL", "http://chroma:8000")
LLM_URL = os.getenv("LLM_URL", "http://oasis-llm:8001")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


class IndexPipeline:
    """End-to-end pipeline: scan → chunk → embed → store in ChromaDB."""

    def __init__(
        self,
        chroma_url: str = CHROMA_URL,
        llm_url: str = LLM_URL,
        embed_model: str = EMBED_MODEL,
    ) -> None:
        self._chroma_url = chroma_url.rstrip("/")
        self._llm_url = llm_url.rstrip("/")
        self._embed_model = embed_model
        self._chunker = CodeChunker()
        self._http = httpx.Client(timeout=120.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_repo(self, repo_path: str, repo_name: str) -> int:
        """Scan, chunk, embed and store an entire repository.

        Returns the number of chunks indexed.
        """
        scanner = RepoScanner(repo_path)
        files = scanner.scan()

        all_chunks: list[dict] = []
        for file_path, language in files:
            chunks = self._chunker.chunk_file(
                file_path=file_path,
                repo=repo_name,
                language=language,
            )
            all_chunks.extend(chunks)

        logger.info("repo=%s: %d total chunks to index", repo_name, len(all_chunks))

        indexed = 0
        for batch_start in range(0, len(all_chunks), _BATCH_SIZE):
            batch = all_chunks[batch_start : batch_start + _BATCH_SIZE]
            embeddings = self._embed_batch([c["content"] for c in batch])
            self._upsert_batch(batch, embeddings)
            indexed += len(batch)
            logger.info("repo=%s: indexed %d/%d chunks", repo_name, indexed, len(all_chunks))

        return indexed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            resp = self._http.post(
                f"{self._llm_url}/embed",
                json={"text": text, "model": self._embed_model},
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
        return embeddings

    def _upsert_batch(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        payload = {
            "ids": [c["id"] for c in chunks],
            "embeddings": embeddings,
            "documents": [c["content"] for c in chunks],
            "metadatas": [
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
        }
        resp = self._http.post(f"{self._chroma_url}/upsert", json=payload)
        resp.raise_for_status()

    def close(self) -> None:
        self._http.close()
