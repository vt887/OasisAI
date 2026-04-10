"""Python AST parser.

Extracts functions, classes, imports, and function calls from a Python
source file using the stdlib ``ast`` module.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedFunction:
    name: str
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)


@dataclass
class ParsedClass:
    name: str
    start_line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class ParsedModule:
    file_path: str
    repo: str
    imports: list[str] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)
    classes: list[ParsedClass] = field(default_factory=list)


class _FunctionCallVisitor(ast.NodeVisitor):
    """Collects all Call node names inside a function body."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class PythonASTParser:
    """Parse a Python source file and return a :class:`ParsedModule`."""

    def parse_file(self, file_path: str | Path, repo: str = "") -> ParsedModule | None:
        path = Path(file_path)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            logger.warning("Syntax error in %s: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return None

        module = ParsedModule(file_path=str(path), repo=repo)

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module.imports.append(node.module)

            # Top-level functions
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                visitor = _FunctionCallVisitor()
                visitor.visit(node)
                module.functions.append(
                    ParsedFunction(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        calls=visitor.calls,
                    )
                )

            # Classes
            elif isinstance(node, ast.ClassDef):
                bases = [
                    b.id if isinstance(b, ast.Name) else ""
                    for b in node.bases
                ]
                methods = [
                    n.name
                    for n in ast.walk(node)
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
                module.classes.append(
                    ParsedClass(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        bases=[b for b in bases if b],
                        methods=methods,
                    )
                )

        return module
