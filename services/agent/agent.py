"""Refactor agent: retrieve context and generate refactor plans and diffs.

Flow:
  1. Semantic search via the gateway search endpoint
  2. Graph expansion via `graph`
  3. Prompt construction
  4. LLM generation via `llm`
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CHROMA_SEARCH_URL = os.getenv(
    "CHROMA_SEARCH_URL", "http://oasis-gateway:8000/search"
)
GRAPH_URL = os.getenv("GRAPH_URL", "http://graph:8003/graph")
LLM_URL = os.getenv("LLM_URL", "http://llm:8001/generate")
LLM_MODEL = os.getenv("LLM_MODEL", "codellama")

_REFACTOR_SYSTEM = (
    "You are an expert software engineer. "
    "Given a user's refactoring instruction and relevant code snippets, "
    "produce:\n"
    "1. A concise plan (numbered steps).\n"
    "2. Unified diff patches (if changes are needed).\n"
    "Do NOT modify files directly. Output only the plan and diffs."
)

_ASK_SYSTEM = (
    "You are an expert software engineer acting as a code assistant. "
    "Answer the user's question based on the provided code context. "
    "Be concise and accurate."
)


class RefactorAgent:
    """Orchestrate context retrieval and LLM generation
    for refactor requests."""

    def __init__(
        self,
        graph_url: str = GRAPH_URL,
        llm_url: str = LLM_URL,
        llm_model: str = LLM_MODEL,
    ) -> None:
        self._graph_url = graph_url
        self._llm_url = llm_url
        self._llm_model = llm_model
        self._http = httpx.Client(timeout=180.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(
        self, question: str, repo: str | None = None, top_k: int = 5
    ) -> dict[str, Any]:
        """Answer a free-form question about the codebase.

        Returns a dict with the generated answer and the source hits.
        """
        results = self._search(question, repo=repo, top_k=top_k)
        context = _format_context(results)
        prompt = f"{context}\n\nQuestion: {question}\n\nAnswer:"
        answer = self._generate(prompt, system=_ASK_SYSTEM)
        return {"answer": answer, "sources": results}

    def refactor(
        self,
        instruction: str,
        repo: str | None = None,
        target_file: str | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Generate a refactor plan and unified-diff patches.

        The returned dict contains `plan`, `patches`, and `sources`.
        """
        results = self._search(instruction, repo=repo, top_k=top_k)
        context = _format_context(results)

        # Optionally expand with graph info
        graph_context = ""
        if target_file and repo:
            graph_context = self._expand_graph(
                file_paths=[target_file], repo=repo
            )

        prompt_parts = [
            f"Refactor instruction: {instruction}",
            "",
            "Relevant code:",
            context,
        ]
        if graph_context:
            prompt_parts.extend(
                [
                    "",
                    "Dependency context:",
                    graph_context,
                ]
            )
        prompt_parts.append("")
        prompt_parts.append("Provide the refactor plan and diffs:")
        prompt = "\n".join(prompt_parts)
        response_text = self._generate(prompt, system=_REFACTOR_SYSTEM)

        # Split plan from diffs (heuristic: unified diff starts with "---")
        plan, patches = _parse_plan_and_patches(response_text)
        return {"plan": plan, "patches": patches, "sources": results}

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search(
        self, query: str, repo: str | None, top_k: int
    ) -> list[dict[str, Any]]:
        """Search the gateway search endpoint and return hit dicts.

        This uses the public gateway `/search` endpoint instead of a
        direct ChromaDB client, which keeps the agent decoupled.
        """
        try:
            payload: dict[str, Any] = {"query": query, "top_k": top_k}
            if repo:
                payload["repo"] = repo

            resp = self._http.post(CHROMA_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", []) if isinstance(data, dict) else []
            hits: list[dict[str, Any]] = []
            for r in results:
                # Expect gateway to return result objects with metadata/docs
                if isinstance(r, dict):
                    hits.append(r)
            return hits
        except Exception as exc:
            logger.warning("Search failed: %s", exc)
            return []

    def _expand_graph(self, file_paths: list[str], repo: str) -> str:
        try:
            resp = self._http.post(
                self._graph_url, json={"file_paths": file_paths, "repo": repo}
            )
            resp.raise_for_status()
            data = resp.json()
            nodes = data.get("nodes", [])
            return "\n".join(
                f"  [{n['kind']}] {n['name']} ({n['file_path']})"
                for n in nodes[:20]
            )
        except Exception as exc:
            logger.warning("Graph expand failed: %s", exc)
            return ""

    def _generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {"prompt": prompt, "model": self._llm_model}
        if system:
            payload["system"] = system
        resp = self._http.post(self._llm_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Guard against untyped JSON from the HTTP call to avoid returning Any
        text: str = ""
        if isinstance(data, dict):
            t = data.get("text")
            if isinstance(t, str):
                text = t
        return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no relevant context found)"
    parts: list[str] = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        if not isinstance(meta, dict):
            meta = {}
        content = r.get("content") or r.get("document", "")
        if not isinstance(content, str):
            content = str(content)
        file_path = meta.get("file_path", "unknown")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        header = f"--- [{i}] {file_path} (lines {start_line}-{end_line}) ---\n"
        parts.append(header + content)
    return "\n\n".join(parts)


def _parse_plan_and_patches(text: str) -> tuple[str, list[str]]:
    """Split LLM output into (plan_text, list_of_diff_strings).

    A unified diff block is identified by consecutive ``--- `` / ``+++ ``
    header lines, which avoids false positives from comment lines or code
    that contains ``--- `` at the start.
    """
    patches: list[str] = []
    plan_lines: list[str] = []
    current_patch: list[str] = []
    in_patch = False
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        # Only start a patch block when we see a proper diff header pair
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
            # A blank line after at least one hunk line closes the patch block
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
