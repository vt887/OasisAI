"""Tests for shared Pydantic schemas."""

from __future__ import annotations

import pytest

from shared.config import settings
from shared.schemas.models import (
    AskRequest,
    ChunkMetadata,
    CodeChunk,
    CodeGraph,
    EmbeddingRequest,
    GenerateRequest,
    GraphEdge,
    GraphNode,
    Language,
    NodeKind,
    RefactorRequest,
    SearchRequest,
)


class TestChunkMetadata:
    def test_defaults(self) -> None:
        meta = ChunkMetadata(
            repo="myrepo",
            file_path="src/main.py",
            module=None,
            start_line=0,
            end_line=0,
            chunk_index=0,
            token_count=0,
            embedding_id=None,
        )
        assert meta.language == Language.UNKNOWN
        assert meta.start_line == 0
        assert meta.end_line == 0
        assert meta.chunk_index == 0

    def test_language_enum(self) -> None:
        meta = ChunkMetadata(
            repo="r",
            file_path="f.py",
            module=None,
            language=Language.PYTHON,
            start_line=0,
            end_line=0,
            chunk_index=0,
            token_count=0,
            embedding_id=None,
        )
        assert meta.language == Language.PYTHON

    def test_negative_line_rejected(self) -> None:
        with pytest.raises(Exception):
            ChunkMetadata(
                repo="r",
                file_path="f.py",
                module=None,
                start_line=-1,
                end_line=0,
                chunk_index=0,
                token_count=0,
                embedding_id=None,
            )


class TestCodeChunk:
    def test_basic(self) -> None:
        meta = ChunkMetadata(
            repo="repo",
            file_path="a.py",
            module=None,
            start_line=0,
            end_line=0,
            chunk_index=0,
            token_count=0,
            embedding_id=None,
        )
        chunk = CodeChunk(
            id="abc123",
            content="def foo(): pass",
            metadata=meta,
            embedding=None,
        )
        assert chunk.embedding is None
        assert chunk.content == "def foo(): pass"

    def test_with_embedding(self) -> None:
        meta = ChunkMetadata(
            repo="repo",
            file_path="a.py",
            module=None,
            start_line=0,
            end_line=0,
            chunk_index=0,
            token_count=0,
            embedding_id=None,
        )
        chunk = CodeChunk(
            id="abc", content="x = 1", metadata=meta, embedding=[0.1, 0.2, 0.3]
        )
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 3


class TestGraphModels:
    def test_graph_node(self) -> None:
        node = GraphNode(
            id="repo::file.py::function::foo",
            kind=NodeKind.FUNCTION,
            name="foo",
            qualified_name=None,
            file_path="file.py",
            ast_hash=None,
        )
        assert node.kind == NodeKind.FUNCTION

    def test_graph_edge(self) -> None:
        edge = GraphEdge(source="a", target="b", relation="calls")
        assert edge.relation == "calls"

    def test_code_graph_empty(self) -> None:
        graph = CodeGraph()
        assert graph.nodes == []
        assert graph.edges == []


class TestRequestSchemas:
    def test_search_request_default_top_k(self) -> None:
        req = SearchRequest(query="database pooling", repo=None, top_k=5)
        assert req.top_k == 5
        assert req.repo is None

    def test_search_request_empty_query_rejected(self) -> None:
        with pytest.raises(Exception):
            SearchRequest(query="", repo=None, top_k=5)

    def test_ask_request(self) -> None:
        req = AskRequest(question="How does X work?", repo="myrepo", top_k=5)
        assert req.top_k == 5

    def test_refactor_request(self) -> None:
        req = RefactorRequest(
            instruction="Extract DB logic",
            repo="r",
            target_file=None,
            top_k=3,
        )
        assert req.top_k == 3

    def test_generate_request_defaults(self) -> None:
        req = GenerateRequest(prompt="hello")
        assert req.model == settings.default_model
        assert req.system is None

    def test_embedding_request_defaults(self) -> None:
        req = EmbeddingRequest(text="hello world")
        assert req.model == settings.embed_model
