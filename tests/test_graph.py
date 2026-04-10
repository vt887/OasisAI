"""Tests for the oasis-graph parser and graph builder modules."""
import sys
import tempfile
from pathlib import Path

import pytest

# Add the service to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "oasis-graph"))

from parser import PythonASTParser, ParsedModule
from graph_builder import GraphBuilder, Graph, Node, Edge


_SAMPLE_PYTHON = """\
import os
from pathlib import Path

def greet(name: str) -> str:
    return f"Hello, {name}"

def main():
    msg = greet("world")
    print(msg)

class Animal:
    def __init__(self, name: str):
        self.name = name

class Dog(Animal):
    def bark(self):
        print("Woof!")
"""


class TestPythonASTParser:
    def setup_method(self):
        self.parser = PythonASTParser()

    def test_parse_imports(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        module = self.parser.parse_file(str(f), repo="test")
        assert module is not None
        assert "os" in module.imports
        assert "pathlib" in module.imports

    def test_parse_functions(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        module = self.parser.parse_file(str(f), repo="test")
        func_names = [fn.name for fn in module.functions]
        assert "greet" in func_names
        assert "main" in func_names

    def test_parse_classes(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        module = self.parser.parse_file(str(f), repo="test")
        class_names = [cls.name for cls in module.classes]
        assert "Animal" in class_names
        assert "Dog" in class_names

    def test_class_inheritance(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        module = self.parser.parse_file(str(f), repo="test")
        dog = next(c for c in module.classes if c.name == "Dog")
        assert "Animal" in dog.bases

    def test_function_calls_detected(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        module = self.parser.parse_file(str(f), repo="test")
        main_fn = next(fn for fn in module.functions if fn.name == "main")
        assert "greet" in main_fn.calls or "print" in main_fn.calls

    def test_syntax_error_returns_none(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(: pass")
        result = self.parser.parse_file(str(f), repo="test")
        assert result is None

    def test_missing_file_returns_none(self):
        result = self.parser.parse_file("/nonexistent/file.py", repo="test")
        assert result is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        module = self.parser.parse_file(str(f), repo="test")
        assert module is not None
        assert module.imports == []
        assert module.functions == []
        assert module.classes == []


class TestGraphBuilder:
    def setup_method(self):
        self.builder = GraphBuilder()

    def test_build_produces_nodes_and_edges(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="testrepo")
        assert isinstance(graph, Graph)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_module_node_present(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="r")
        kinds = [n.kind for n in graph.nodes]
        assert "module" in kinds

    def test_function_nodes_present(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="r")
        func_nodes = [n for n in graph.nodes if n.kind == "function"]
        func_names = [n.name for n in func_nodes]
        assert "greet" in func_names
        assert "main" in func_names

    def test_class_nodes_present(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="r")
        class_nodes = [n for n in graph.nodes if n.kind == "class"]
        class_names = [n.name for n in class_nodes]
        assert "Animal" in class_names
        assert "Dog" in class_names

    def test_inherits_edge_present(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="r")
        inherits_edges = [e for e in graph.edges if e.relation == "inherits"]
        assert len(inherits_edges) > 0

    def test_to_dict(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(_SAMPLE_PYTHON)
        graph = self.builder.build_from_files([str(f)], repo="r")
        data = graph.to_dict()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_empty_file_list(self):
        graph = self.builder.build_from_files([], repo="r")
        assert graph.nodes == []
        assert graph.edges == []
