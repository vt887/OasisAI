"""Cross-repo code graph utilities.

Provides a lightweight node/edge graph for symbols across multiple
repositories. The implementation is intentionally simple and persisted to
disk as JSON for incremental updates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Simple on-disk store path (relative to repo root)
_GRAPH_STORE = Path(".oasis_graph.json")


def _load_store() -> dict[str, Any]:
    if not _GRAPH_STORE.exists():
        return {"nodes": {}, "edges": []}
    try:
        loaded = json.loads(_GRAPH_STORE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return cast(dict[str, Any], loaded)
        return {"nodes": {}, "edges": []}
    except Exception:
        logger.exception("Failed to load graph store")
        return {"nodes": {}, "edges": []}


def _save_store(store: dict[str, Any]) -> None:
    _GRAPH_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def make_node_id(repo: str, file_path: str, qualified_name: str) -> str:
    return f"{repo}:{file_path}:{qualified_name}"


def build_from_parsed_modules(parsed_modules: list[Any]) -> None:
    """Build or update the graph store from a list of ParsedModule objects.

    Each ParsedModule is expected to have attributes: file_path, repo,
    imports, functions (with name/start/end/calls) and classes.
    """
    store = _load_store()
    nodes = cast(dict[str, dict[str, Any]], store.get("nodes", {}))
    edges = cast(list[dict[str, Any]], store.get("edges", []))

    for mod in parsed_modules:
        repo = getattr(mod, "repo", "")
        file_path = getattr(mod, "file_path", "")
        module_name = Path(file_path).stem

        # add function nodes
        for f in getattr(mod, "functions", []):
            qname = f"{module_name}.{f.name}"
            nid = make_node_id(repo, file_path, qname)
            nodes[nid] = {
                "id": nid,
                "repo": repo,
                "file_path": file_path,
                "qualified_name": qname,
                "kind": "function",
                "start_line": f.start_line,
                "end_line": f.end_line,
                "calls": getattr(f, "calls", []),
            }

        # add class nodes
        for c in getattr(mod, "classes", []):
            qname = f"{module_name}.{c.name}"
            nid = make_node_id(repo, file_path, qname)
            nodes[nid] = {
                "id": nid,
                "repo": repo,
                "file_path": file_path,
                "qualified_name": qname,
                "kind": "class",
                "start_line": c.start_line,
                "end_line": c.end_line,
                "bases": getattr(c, "bases", []),
                "methods": getattr(c, "methods", []),
            }

        # add import edges
        for imp in getattr(mod, "imports", []):
            # create a module-level node for import source
            src_q = imp
            src_id = make_node_id("<external>", src_q, "<module>")
            # target is the module itself
            tgt_id = make_node_id(repo, file_path, module_name)
            edges.append(
                {"source": src_id, "target": tgt_id, "relation": "imports"}
            )

    store["nodes"] = nodes
    store["edges"] = edges
    _save_store(store)


def get_callers(qualified_name: str) -> list[str]:
    """Return node ids of functions that call *qualified_name*.

    The qualified_name may be partial; this scans call lists for matches.
    """
    store = _load_store()
    nodes = store.get("nodes", {})
    callers: list[str] = []
    for nid, nd in nodes.items():
        calls = nd.get("calls") or []
        for c in calls:
            if c.endswith(qualified_name) or c == qualified_name:
                callers.append(nid)
                break
    return callers


def get_cross_repo_dependencies(qualified_name: str) -> list[str]:
    """Return related nodes across repos for *qualified_name*.

    This includes callers, callees (functions called by the symbol), and
    import relations for modules containing the symbol.
    """
    store = _load_store()
    nodes = store.get("nodes", {})
    edges = store.get("edges", [])
    result: set[str] = set()

    # find node ids matching qualified_name
    matching = [
        nid
        for nid, n in nodes.items()
        if n.get("qualified_name", "").endswith(qualified_name)
    ]
    for nid in matching:
        result.add(nid)

        # callers (functions that reference this qualified name)
        callers = get_callers(qualified_name)
        for c in callers:
            result.add(c)

        # callees: functions that this node calls (if recorded)
        node = nodes.get(nid, {})
        for callee in node.get("calls", []) or []:
            # find node(s) matching callee qualified name
            for nid2, n2 in nodes.items():
                if n2.get("qualified_name") == callee or n2.get(
                    "qualified_name", ""
                ).endswith(callee):
                    result.add(nid2)

        # imports: include edges related to the module containing this symbol
        module_name = (
            nodes.get(nid, {}).get("qualified_name", "").split(".")[0]
        )
        for e in edges:
            if e.get("target", "").endswith(module_name) or e.get(
                "source", ""
            ).endswith(module_name):
                if e.get("source"):
                    result.add(e.get("source"))
                if e.get("target"):
                    result.add(e.get("target"))

    return list(result)


def get_related_symbols(qualified_name: str, depth: int = 1) -> list[str]:
    """Return related symbols up to *depth* via callers/callees.

    This performs a simple BFS over call edges recorded in nodes.calls.
    """
    store = _load_store()
    nodes = store.get("nodes", {})
    q_to_id = {n.get("qualified_name", ""): nid for nid, n in nodes.items()}

    start_ids = [
        nid
        for nid, n in nodes.items()
        if n.get("qualified_name", "").endswith(qualified_name)
    ]
    seen: set[str] = set(start_ids)
    frontier: list[str] = list(start_ids)
    for _ in range(depth):
        next_frontier: list[str] = []
        for fid in frontier:
            node = nodes.get(fid, {})
            for callee in node.get("calls", []):
                # find node id for callee
                cid = q_to_id.get(callee)
                if cid is not None and cid not in seen:
                    seen.add(str(cid))
                    next_frontier.append(str(cid))
        frontier = next_frontier
    return list(seen)
