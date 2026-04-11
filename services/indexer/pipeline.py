from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

import chromadb
import httpx
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings
from chunker import CodeChunker
from scanner import RepoScanner

from shared.config import settings

logger = logging.getLogger(__name__)


class IndexPipeline:
    def __init__(
        self,
        chroma_host: str = settings.chroma_host,
        chroma_port: int = settings.chroma_port,
        llm_url: str = settings.llm_url,
        embed_model: str = settings.embed_model,
    ) -> None:
        self._chroma_host = chroma_host
        self._chroma_port = chroma_port
        self._llm_url = llm_url.rstrip("/")
        self._embed_model = embed_model
        self._chunker = CodeChunker()
        self._http: httpx.Client | None = None
        self._chroma: ClientAPI | None = None
        self._collection: Collection | None = None
        self._initialized = False
        self._hash_file = Path(".oasis_index_state.json")
        self._indexed_state = self._load_state()

    def index_repo(self, repo_path: str, repo_name: str) -> int:
        """Index a repository and return number of chunks indexed.

        This implementation streams chunks per-file and processes them in
        batches to avoid building a large in-memory list of all chunks.
        """
        logger.info("Start indexing repo %s (%s)", repo_name, repo_path)
        self._ensure_initialized()
        scanner = RepoScanner(repo_path)

        indexed = 0
        batch: list[dict[str, Any]] = []

        for file_path, language in scanner.scan():
            chunks = self._chunk_file_if_changed(
                str(file_path), language, repo_name
            )
            if not chunks:
                logger.debug("No changes in %s; skipping", file_path)
                continue

            for c in chunks:
                batch.append(c)
                if len(batch) >= settings.batch_size:
                    embeddings = self._embed_batch(
                        [b["content"] for b in batch]
                    )
                    self._upsert_batch(batch, embeddings)
                    indexed += len(batch)
                    batch.clear()

        # Flush remaining
        if batch:
            embeddings = self._embed_batch([b["content"] for b in batch])
            self._upsert_batch(batch, embeddings)
            indexed += len(batch)
        self._save_state()
        logger.info("Indexing complete: %d chunks indexed", indexed)
        return indexed

    def _chunk_file_if_changed(
        self, file_path: str, language: str, repo_name: str
    ) -> list[dict[str, Any]]:
        digest = self._file_hash(file_path)
        key = f"{repo_name}:{file_path}"
        if self._indexed_state.get(key) == digest:
            return []
        chunks: list[dict[str, Any]] = self._chunker.chunk_file(
            file_path=file_path, repo=repo_name, language=language
        )
        self._indexed_state[key] = digest
        return chunks

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._ensure_initialized()
        if self._http is None:
            raise RuntimeError("HTTP client is not available")
        http_client: httpx.Client = self._http

        def embed_one(text: str) -> list[float]:
            for attempt in range(settings.retries + 1):
                try:
                    resp = http_client.post(
                        f"{self._llm_url}/embed",
                        json={"text": text, "model": self._embed_model},
                        timeout=settings.request_timeout_seconds,
                    )
                    resp.raise_for_status()
                    return cast(list[float], resp.json()["embedding"])
                except Exception:
                    if attempt >= settings.retries:
                        raise
                    time.sleep(settings.backoff_seconds * (2**attempt))
            return []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.max_workers
        ) as ex:
            return list(ex.map(embed_one, texts))

    def _upsert_batch(
        self, chunks: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
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
        if self._initialized:
            return
        if self._http is None:
            self._http = httpx.Client(
                timeout=settings.http_client_timeout_seconds
            )
        try:
            self._chroma = chromadb.HttpClient(
                host=self._chroma_host,
                port=self._chroma_port,
                settings=Settings(
                    anonymized_telemetry=settings.chroma_anonymized_telemetry
                ),
            )
            self._collection = self._chroma.get_or_create_collection(
                name="oasis_code", metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            self._chroma = None
            self._collection = None
        self._initialized = True

    def _file_hash(self, file_path: str) -> str:
        return hashlib.sha256(Path(file_path).read_bytes()).hexdigest()

    def _load_state(self) -> dict[str, str]:
        if not self._hash_file.exists():
            return {}
        try:
            return cast(
                dict[str, str], json.loads(self._hash_file.read_text())
            )
        except Exception:
            return {}

    def _save_state(self) -> None:
        self._hash_file.write_text(json.dumps(self._indexed_state))
