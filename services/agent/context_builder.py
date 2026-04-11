"""Smart context builder for multi-repo OasisAI (agent package).

This is the same implementation previously placed under
`services/oasis_agent` but moved into the existing `services.agent`
package as requested so the `agent` package owns the module.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from shared.config import settings
from shared.graph import cross_repo
from shared.resilience import async_retry
from storage.chroma.client import ChromaClient

logger = logging.getLogger(__name__)


class ContextBundle(dict[str, Any]):
    """Simple container for ordered context chunks and provenance.

    Keys:
        ordered_chunks: list[dict]
        total_tokens: int
        provenance: list[dict]
    """


async def build_context(
    query: str,
    max_tokens: int = 1500,
    repo_filters: list[str] | None = None,
    top_k: int = 20,
    debug: bool = False,
) -> ContextBundle:
    chroma = ChromaClient()

    emb = await _embed_query(query)
    where: dict[str, Any] | None = None
    if repo_filters:
        where = {"repo": repo_filters}

    hits = chroma.query(query_embedding=emb, top_k=top_k, where=where)

    candidates: list[dict[str, Any]] = []
    for h in hits:
        meta = h.get("metadata", {})
        token_count = int(meta.get("token_count", 0) or 0)
        candidates.append(
            {
                "chunk_id": h.get("id"),
                "text": h.get("document"),
                "metadata": meta,
                "distance": float(h.get("distance", 0.0)),
                "semantic_score": 1.0 - float(h.get("distance", 0.0)),
                "token_count": token_count,
            }
        )

    expanded: list[dict[str, Any]] = list(candidates)
    query_symbol = None
    if "." in query:
        query_symbol = query.split(".")[-1]

    seeds: list[dict[str, Any]] = []
    if query_symbol:
        for c in candidates:
            syms = c.get("metadata", {}).get("symbols") or []
            for s in syms:
                if s.get("name") == query_symbol or s.get(
                    "qualified_name", ""
                ).endswith(query_symbol):
                    seeds.append(c)
                    break

    if seeds:
        related_names: set[str] = set()
        for s in seeds:
            syms = s.get("metadata", {}).get("symbols") or []
            for sym in syms:
                qn = sym.get("qualified_name")
                if not qn:
                    continue
                related = cross_repo.get_related_symbols(qn, depth=1)
                for rid in related:
                    parts = rid.split(":")
                    if len(parts) >= 3:
                        related_qn = parts[2]
                        related_names.add(related_qn)

        for c in candidates:
            syms = c.get("metadata", {}).get("symbols") or []
            for s in syms:
                if s.get("qualified_name") in related_names:
                    if c not in expanded:
                        expanded.append(c)
                        break

    selected = rank_and_budget(expanded, query, max_tokens)

    grouped: dict[str, list[dict[str, Any]]] = {}
    provenance: list[dict[str, Any]] = []
    total = 0
    for c in selected:
        repo = c.get("metadata", {}).get("repo") or "<unknown>"
        grouped.setdefault(repo, []).append(c)
        provenance.append(
            {
                "chunk_id": c.get("chunk_id"),
                "score": c.get("semantic_score"),
                "reasons": ["semantic"],
            }
        )
        total += int(c.get("token_count", 0) or 0)

    bundle = ContextBundle(
        ordered_chunks=selected,
        total_tokens=total,
        grouped_by_repo=grouped,
        provenance=provenance,
    )
    if debug:
        bundle["debug"] = {"raw_hits": hits}
    return bundle


async def _embed_query(query: str) -> list[float]:
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds
    ) as client:

        async def _call() -> list[float]:
            response = await client.post(
                f"{settings.llm_url}/embed",
                json={"text": query, "model": settings.embed_model},
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding") if isinstance(data, dict) else []
            return list(embedding) if isinstance(embedding, list) else []

        return await async_retry(
            _call,
            retries=settings.retries,
            backoff_seconds=settings.backoff_seconds,
        )


def rank_and_budget(
    candidates: list[dict[str, Any]], query: str, max_tokens: int
) -> list[dict[str, Any]]:
    for c in candidates:
        if not c.get("token_count"):
            c["token_count"] = max(20, int(len(c.get("text", "")) / 40))
    candidates.sort(
        key=lambda x: (
            x.get("semantic_score", 0.0) / max(1, x.get("token_count", 1))
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    tokens_used = 0
    for c in candidates:
        t = int(c.get("token_count", 0) or 0)
        if tokens_used + t > max_tokens:
            continue
        selected.append(c)
        tokens_used += t
        if tokens_used >= max_tokens:
            break
    return selected


def expand_by_symbol(
    seed_chunks: list[dict[str, Any]],
    depth: int = 1,
    max_per_symbol: int = 5,
) -> list[dict[str, Any]]:
    from shared.graph import cross_repo as _cross

    related: list[dict[str, Any]] = list(seed_chunks)
    seen: set[str] = {
        str(c.get("chunk_id"))
        for c in seed_chunks
        if c.get("chunk_id") is not None
    }
    for c in seed_chunks:
        syms = c.get("metadata", {}).get("symbols") or []
        for sym in syms:
            qn = sym.get("qualified_name")
            if not qn:
                continue
            nodes = _cross.get_related_symbols(qn, depth=depth)
            for nid in nodes:
                parts = nid.split(":")
                if len(parts) < 3:
                    continue
                rq = parts[2]
                for cand in seed_chunks:
                    csyms = cand.get("metadata", {}).get("symbols") or []
                    for cs in csyms:
                        if (
                            cs.get("qualified_name") == rq
                            and cand.get("chunk_id") is not None
                            and str(cand.get("chunk_id")) not in seen
                        ):
                            related.append(cand)
                            seen.add(str(cand.get("chunk_id")))
                            if len(related) >= max_per_symbol:
                                break
                    if len(related) >= max_per_symbol:
                        break
                if len(related) >= max_per_symbol:
                    break
    return related
