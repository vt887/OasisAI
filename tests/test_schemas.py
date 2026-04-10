"""Tests for shared Pydantic schemas."""
import pytest
from shared.schemas.models import (
    ChunkMetadata,
    CodeChunk,
    Language,
    NodeKind,
    GraphNode,
    GraphEdge,
    CodeGraph,
    SearchRequest,
    AskRequest,
    RefactorRequest,
    GenerateRequest,
    EmbeddingRequest,
)


class TestChunkMetadata:
    def test_defaults(self):
        meta = ChunkMetadata(repo="myrepo", file_path="src/main.py")
        assert meta.language == Language.UNKNOWN
        assert meta.start_line == 0
        assert meta.end_line == 0
        assert meta.chunk_index == 0

    def test_language_enum(self):
        meta = ChunkMetadata(repo="r", file_path="f.py", language="python")
        assert meta.language == Language.PYTHON

    def test_negative_line_rejected(self):
        with pytest.raises(Exception):
            ChunkMetadata(repo="r", file_path="f.py", start_line=-1)


class TestCodeChunk:
    def test_basic(self):
        meta = ChunkMetadata(repo="repo", file_path="a.py")
        chunk = CodeChunk(id="abc123", content="def foo(): pass", metadata=meta)
        assert chunk.embedding is None
        assert chunk.content == "def foo(): pass"

    def test_with_embedding(self):
        meta = ChunkMetadata(repo="repo", file_path="a.py")
        chunk = CodeChunk(
            id="abc", content="x = 1", metadata=meta, embedding=[0.1, 0.2, 0.3]
        )
        assert len(chunk.embedding) == 3


class TestGraphModels:
    def test_graph_node(self):
        node = GraphNode(
            id="repo::file.py::function::foo",
            kind=NodeKind.FUNCTION,
            name="foo",
            file_path="file.py",
        )
        assert node.kind == NodeKind.FUNCTION

    def test_graph_edge(self):
        edge = GraphEdge(source="a", target="b", relation="calls")
        assert edge.relation == "calls"

    def test_code_graph_empty(self):
        graph = CodeGraph()
        assert graph.nodes == []
        assert graph.edges == []


class TestRequestSchemas:
    def test_search_request_default_top_k(self):
        req = SearchRequest(query="database pooling")
        assert req.top_k == 5
        assert req.repo is None

    def test_search_request_empty_query_rejected(self):
        with pytest.raises(Exception):
            SearchRequest(query="")

    def test_ask_request(self):
        req = AskRequest(question="How does X work?", repo="myrepo")
        assert req.top_k == 5

    def test_refactor_request(self):
        req = RefactorRequest(instruction="Extract DB logic", repo="r", top_k=3)
        assert req.top_k == 3

    def test_generate_request_defaults(self):
        req = GenerateRequest(prompt="hello")
        assert req.model == "codellama"
        assert req.system is None

    def test_embedding_request_defaults(self):
        req = EmbeddingRequest(text="hello world")
        assert req.model == "nomic-embed-text"
