"""ChromaDB client wrapper.

Provides a thin, typed interface around the ChromaDB HTTP client so that
all OasisAI services interact with ChromaDB through a single abstraction.
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "oasis_code"


class ChromaClient:
    """Thin wrapper around ChromaDB for code chunk storage and retrieval."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection_name: str = _DEFAULT_COLLECTION,
    ) -> None:
        self._collection_name = collection_name
        self._client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._get_or_create_collection()
        logger.info(
            "ChromaClient connected to %s:%s, collection=%s",
            host,
            port,
            collection_name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_collection(self) -> Any:
        return self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Upsert a batch of code chunks with their embeddings."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted %d chunks", len(ids))

    def delete_by_repo(self, repo: str) -> None:
        """Remove all chunks belonging to a given repository."""
        self._collection.delete(where={"repo": repo})
        logger.info("Deleted all chunks for repo=%s", repo)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top-k most similar chunks to the query embedding.

        Returns a list of dicts with keys: id, document, metadata, distance.
        """
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        hits: list[dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                }
            )
        return hits

    def count(self) -> int:
        """Return the total number of stored chunks."""
        # The underlying client may return a value typed as Any; coerce to int
        try:
            return int(self._collection.count())
        except Exception:
            logger.exception("Unable to coerce collection.count() to int")
            return 0
