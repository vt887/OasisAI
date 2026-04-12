"""ChromaDB client wrapper.

Provides a thin, typed interface around the ChromaDB HTTP client so that
all OasisAI services interact with ChromaDB through a single abstraction.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast
from uuid import UUID

import chromadb
from chromadb.config import Settings

from shared.config import settings

logger = logging.getLogger(__name__)


class ChromaClient:
    """Thin wrapper around ChromaDB for code chunk storage and retrieval."""

    def __init__(
        self,
        host: str = settings.chroma_host,
        port: int = settings.chroma_port,
        collection_name: str = settings.chroma_collection,
    ) -> None:
        # prefer explicit arg, then settings value
        self._collection_name = collection_name
        self._client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info(
            "ChromaClient connected to %s:%s, collection=%s",
            host,
            port,
            collection_name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_collection_id(self) -> UUID:
        tenant = self._client.tenant
        database = self._client.database
        raw = cast(
            dict[str, Any],
            self._client._server._make_request(  # type: ignore[attr-defined]
                "post",
                f"/tenants/{tenant}/databases/{database}/collections",
                json={
                    "name": self._collection_name,
                    "metadata": {"hnsw:space": "cosine"},
                    "configuration": None,
                    "get_or_create": True,
                },
            ),
        )
        collection_id = raw.get("id")
        if not isinstance(collection_id, str):
            raise RuntimeError("Chroma collection response missing id")
        return UUID(collection_id)

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
        tenant = self._client.tenant
        database = self._client.database
        collection_id = self._get_or_create_collection_id()
        self._client._server._make_request(  # type: ignore[attr-defined]
            "post",
            f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/upsert",
            json={
                "ids": ids,
                "embeddings": embeddings,
                "metadatas": metadatas,
                "documents": documents,
                "uris": None,
            },
        )
        logger.debug("Upserted %d chunks", len(ids))

    def delete_by_repo(self, repo: str) -> None:
        """Remove all chunks belonging to a given repository."""
        tenant = self._client.tenant
        database = self._client.database
        collection_id = self._get_or_create_collection_id()
        self._client._server._make_request(  # type: ignore[attr-defined]
            "post",
            f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/delete",
            json={
                "ids": None,
                "where": {"repo": repo},
                "where_document": None,
            },
        )
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
        tenant = self._client.tenant
        database = self._client.database
        collection_id = self._get_or_create_collection_id()
        results = cast(
            dict[str, Any],
            self._client._server._make_request(  # type: ignore[attr-defined]
                "post",
                f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/query",
                json={
                    "query_embeddings": [query_embedding],
                    "n_results": top_k,
                    "where": where,
                    "where_document": None,
                    "include": ["documents", "metadatas", "distances"],
                },
            ),
        )

        hits: list[dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
            decoded_meta = meta if isinstance(meta, dict) else {}
            symbols = decoded_meta.get("symbols")
            if isinstance(symbols, str):
                try:
                    decoded_symbols = json.loads(symbols)
                except json.JSONDecodeError:
                    decoded_symbols = symbols
                decoded_meta = {**decoded_meta, "symbols": decoded_symbols}
            hits.append(
                {
                    "id": chunk_id,
                    "document": doc,
                    "metadata": decoded_meta,
                    "distance": dist,
                }
            )
        return hits

    def count(self) -> int:
        """Return the total number of stored chunks."""
        try:
            tenant = self._client.tenant
            database = self._client.database
            collection_id = self._get_or_create_collection_id()
            raw = self._client._server._make_request(  # type: ignore[attr-defined]
                "get",
                f"/tenants/{tenant}/databases/{database}/collections/{collection_id}/count",
            )
            return int(raw)
        except Exception:
            logger.exception("Unable to coerce collection.count() to int")
            return 0

    def heartbeat(self) -> Any:
        return self._client.heartbeat()
