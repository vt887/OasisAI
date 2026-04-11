"""Graph builder: turns parsed modules into a directed dependency graph."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .parser import ParsedModule

_PARSER_MODULE: ModuleType = importlib.import_module(
    f"{__package__}.parser" if __package__ else "parser"
)

logger = logging.getLogger(__name__)


@dataclass
class Node:
    id: str
    kind: str  # "function" | "class" | "module" | "import"
    name: str
    file_path: str
    start_line: int = 0
    end_line: int = 0
    repo: str = ""


@dataclass
class Edge:
    source: str
    target: str
    relation: str  # "calls" | "imports" | "inherits" | "defines"


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "nodes": [vars(n) for n in self.nodes],
            "edges": [vars(e) for e in self.edges],
        }


class GraphBuilder:
    """Build a Graph from ParsedModule objects."""

    def __init__(self) -> None:
        self._parser = _PARSER_MODULE.PythonASTParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_from_files(self, file_paths: list[str], repo: str = "") -> Graph:
        """Parse *file_paths* and return a combined dependency graph."""
        graph = Graph()
        for path in file_paths:
            module = self._parser.parse_file(path, repo=repo)
            if module:
                self._add_module(graph, module)
        return graph

    def build_from_module(self, module: ParsedModule) -> Graph:
        graph = Graph()
        self._add_module(graph, module)
        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_module(self, graph: Graph, module: ParsedModule) -> None:
        module_id = _make_id("module", module.repo, module.file_path, "")
        graph.nodes.append(
            Node(
                id=module_id,
                kind="module",
                name=module.file_path,
                file_path=module.file_path,
                repo=module.repo,
            )
        )

        # Imports
        for imp in module.imports:
            imp_id = _make_id("import", module.repo, module.file_path, imp)
            graph.nodes.append(
                Node(
                    id=imp_id,
                    kind="import",
                    name=imp,
                    file_path=module.file_path,
                    repo=module.repo,
                )
            )
            graph.edges.append(
                Edge(source=module_id, target=imp_id, relation="imports")
            )

        # Functions
        for func in module.functions:
            func_id = _make_id(
                "function", module.repo, module.file_path, func.name
            )
            graph.nodes.append(
                Node(
                    id=func_id,
                    kind="function",
                    name=func.name,
                    file_path=module.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    repo=module.repo,
                )
            )
            graph.edges.append(
                Edge(source=module_id, target=func_id, relation="defines")
            )

            for callee in func.calls:
                callee_id = _make_id(
                    "function", module.repo, module.file_path, callee
                )
                graph.edges.append(
                    Edge(source=func_id, target=callee_id, relation="calls")
                )

        # Classes
        for cls in module.classes:
            cls_id = _make_id("class", module.repo, module.file_path, cls.name)
            graph.nodes.append(
                Node(
                    id=cls_id,
                    kind="class",
                    name=cls.name,
                    file_path=module.file_path,
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    repo=module.repo,
                )
            )
            graph.edges.append(
                Edge(source=module_id, target=cls_id, relation="defines")
            )

            for base in cls.bases:
                base_id = _make_id(
                    "class", module.repo, module.file_path, base
                )
                graph.edges.append(
                    Edge(source=cls_id, target=base_id, relation="inherits")
                )


def _make_id(kind: str, repo: str, file_path: str, name: str) -> str:
    return f"{repo}::{file_path}::{kind}::{name}"
