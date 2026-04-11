from __future__ import annotations

import logging
from typing import Any

import httpx

from shared.config import settings
from shared.resilience import async_retry

logger = logging.getLogger(__name__)

CHROMA_SEARCH_URL = "http://oasis-gateway:8000/search"
GRAPH_URL = "http://graph:8003/graph"
LLM_URL = "http://llm:8001/generate"
LLM_MODEL = "codellama"

_REFACTOR_SYSTEM = (
    "You are an expert software engineer. Output plan and unified diffs only."
)
_ASK_SYSTEM = "You are an expert software engineer acting as a code assistant."


class RefactorAgent:
    def __init__(
        self,
        graph_url: str = GRAPH_URL,
        llm_url: str = LLM_URL,
        llm_model: str = LLM_MODEL,
    ) -> None:
        self._graph_url = graph_url
        self._llm_url = llm_url
        self._llm_model = llm_model
        self._http = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        )

    async def ask(
        self, question: str, repo: str | None = None, top_k: int = 5
    ) -> dict[str, Any]:
        results = await self._search(question, repo=repo, top_k=top_k)
        prompt = (
            f"{_format_context(results)}\n\nQuestion: {question}\n\nAnswer:"
        )
        answer = await self._generate(prompt, system=_ASK_SYSTEM)
        return {"answer": answer, "sources": results}

    async def refactor(
        self,
        instruction: str,
        repo: str | None = None,
        target_file: str | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        results = await self._search(instruction, repo=repo, top_k=top_k)
        graph_context = ""
        if target_file and repo:
            graph_context = await self._expand_graph(
                file_paths=[target_file], repo=repo
            )
        prompt = "\n".join(
            [
                f"Refactor instruction: {instruction}",
                "",
                "Relevant code:",
                _format_context(results),
                "",
                "Dependency context:",
                graph_context,
                "",
                "Provide plan and diffs:",
            ]
        )
        response_text = await self._generate(prompt, system=_REFACTOR_SYSTEM)
        plan, patches = _parse_plan_and_patches(response_text)
        return {"plan": plan, "patches": patches, "sources": results}

    async def _search(
        self, query: str, repo: str | None, top_k: int
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"query": query, "top_k": top_k}
        if repo:
            payload["repo"] = repo

        async def _call() -> list[dict[str, Any]]:
            resp = await self._http.post(CHROMA_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", []) if isinstance(data, dict) else []

        try:
            return await async_retry(
                _call,
                retries=settings.retries,
                backoff_seconds=settings.backoff_seconds,
            )
        except Exception:
            logger.exception("search failed")
            return []

    async def _expand_graph(self, file_paths: list[str], repo: str) -> str:
        async def _call() -> str:
            resp = await self._http.post(
                self._graph_url, json={"file_paths": file_paths, "repo": repo}
            )
            resp.raise_for_status()
            data = resp.json()
            nodes = data.get("nodes", [])
            return "\n".join(
                f"  [{n['kind']}] {n['name']} ({n['file_path']})"
                for n in nodes[:20]
            )

        try:
            return await async_retry(
                _call,
                retries=settings.retries,
                backoff_seconds=settings.backoff_seconds,
            )
        except Exception:
            return ""

    async def _generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {"prompt": prompt, "model": self._llm_model}
        if system:
            payload["system"] = system

        async def _call() -> str:
            resp = await self._http.post(self._llm_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            t = data.get("text") if isinstance(data, dict) else ""
            return t if isinstance(t, str) else ""

        return await async_retry(
            _call,
            retries=settings.retries,
            backoff_seconds=settings.backoff_seconds,
        )


def _format_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no relevant context found)"
    parts: list[str] = []
    for i, r in enumerate(results, 1):
        meta = (
            r.get("metadata", {})
            if isinstance(r.get("metadata", {}), dict)
            else {}
        )
        content = r.get("content") or r.get("document", "")
        if not isinstance(content, str):
            content = str(content)
        header = (
            f"--- [{i}] {meta.get('file_path', 'unknown')} "
            f"(lines {meta.get('start_line', '?')}-"
            f"{meta.get('end_line', '?')}) ---"
        )
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


def _parse_plan_and_patches(text: str) -> tuple[str, list[str]]:
    patches: list[str] = []
    plan_lines: list[str] = []
    current_patch: list[str] = []
    in_patch = False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            not in_patch
            and line.startswith("--- ")
            and i + 1 < len(lines)
            and lines[i + 1].startswith("+++ ")
        ):
            in_patch = True
            current_patch = [line]
        elif in_patch:
            current_patch.append(line)
            if line == "" and len(current_patch) > 4:
                patches.append("\n".join(current_patch))
                current_patch = []
                in_patch = False
        else:
            plan_lines.append(line)
        i += 1
    if current_patch:
        patches.append("\n".join(current_patch))
    return "\n".join(plan_lines).strip(), patches
