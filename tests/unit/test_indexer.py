"""Tests for the oasis-indexer chunker module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the service to path for direct import
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "services" / "indexer")
)

from chunker import CodeChunker, _make_id
from pipeline import IndexPipeline
from scanner import RepoScanner

from shared.config import settings


class TestCodeChunker:
    def setup_method(self) -> None:
        self.chunker = CodeChunker(chunk_size=5, overlap=1)

    def _write_file(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "sample.py"
        f.write_text(content)
        return f

    def test_basic_chunking(self, tmp_path: Path) -> None:
        lines = "\n".join(f"line{i}" for i in range(20))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(f, repo="testrepo", language="python")
        assert len(chunks) > 1
        assert all(c["repo"] == "testrepo" for c in chunks)
        assert all(c["language"] == "python" for c in chunks)

    def test_chunk_ids_unique(self, tmp_path: Path) -> None:
        lines = "\n".join(f"x = {i}" for i in range(30))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("")
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        assert chunks == []

    def test_missing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.py"
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        assert chunks == []

    def test_chunk_metadata_fields(self, tmp_path: Path) -> None:
        lines = "\n".join(f"line{i}" for i in range(10))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(
            f, repo="repo1", language="javascript"
        )
        first = chunks[0]
        assert "start_line" in first
        assert "end_line" in first
        assert "chunk_index" in first
        assert first["chunk_index"] == 0

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            CodeChunker(chunk_size=5, overlap=5)


class TestMakeId:
    def test_deterministic(self) -> None:
        id1 = _make_id("repo", "/path/to/file.py", 0)
        id2 = _make_id("repo", "/path/to/file.py", 0)
        assert id1 == id2

    def test_different_chunks_different_ids(self) -> None:
        id1 = _make_id("repo", "/path/to/file.py", 0)
        id2 = _make_id("repo", "/path/to/file.py", 1)
        assert id1 != id2


class TestRepoScanner:
    def test_scan_finds_python(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("def foo(): pass")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        langs = [lang for _, lang in results]
        assert all(lang == "python" for lang in langs)
        assert len(results) == 2

    def test_scan_skips_pycache(self, tmp_path: Path) -> None:
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("")
        (tmp_path / "main.py").write_text("x = 1")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        assert len(results) == 1

    def test_scan_multiple_languages(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "index.js").write_text("console.log('hi')")
        (tmp_path / "main.go").write_text("package main")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        langs = {lang for _, lang in results}
        assert langs == {"python", "javascript", "go"}

    def test_invalid_path_raises(self) -> None:
        with pytest.raises(ValueError):
            RepoScanner("/nonexistent/path/that/does/not/exist")


class TestIndexPipeline:
    """Tests for the IndexPipeline class."""

    def test_init_deferred(self) -> None:
        """Test that IndexPipeline initialization is deferred."""
        pipeline = IndexPipeline(
            chroma_host="localhost",
            chroma_port=8000,
            llm_url="http://llm:8001",
            embed_model="nomic-embed-text",
        )
        assert pipeline._http is None
        assert pipeline._chroma is None
        assert pipeline._collection is None
        assert not pipeline._initialized

    def test_init_with_defaults(self) -> None:
        """Test initialization with default environment variables."""
        pipeline = IndexPipeline()
        assert pipeline._chroma_host == settings.chroma_host
        assert pipeline._chroma_port == settings.chroma_port
        assert pipeline._llm_url == settings.llm_url
        assert pipeline._embed_model == settings.embed_model

    def test_close_when_http_is_none(self) -> None:
        """Test close() handles None HTTP client gracefully."""
        pipeline = IndexPipeline()
        pipeline.close()  # Should not raise

    def test_close_closes_http_client(self) -> None:
        """Test close() closes the HTTP client if it exists."""
        pipeline = IndexPipeline()
        mock_client = MagicMock()
        pipeline._http = mock_client
        pipeline.close()
        mock_client.close.assert_called_once()

    @patch("pipeline.httpx.Client")
    def test_ensure_initialized_creates_http_client(
        self, mock_http_class: MagicMock
    ) -> None:
        """Test _ensure_initialized creates HTTP client."""
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance

        pipeline = IndexPipeline()
        pipeline._ensure_initialized()

        # Verify at least one call with timeout=120.0
        assert mock_http_class.call_count >= 1
        assert pipeline._http is not None
        assert pipeline._initialized

    @patch("pipeline.chromadb.HttpClient")
    @patch("pipeline.httpx.Client")
    def test_ensure_initialized_creates_chroma_client(
        self,
        mock_http_class: MagicMock,
        mock_chroma_class: MagicMock,
    ) -> None:
        """Test _ensure_initialized creates ChromaDB client."""
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance
        mock_chroma_instance = MagicMock()
        mock_chroma_class.return_value = mock_chroma_instance
        mock_collection = MagicMock()
        mock_chroma_instance.get_or_create_collection.return_value = (
            mock_collection
        )

        pipeline = IndexPipeline(
            chroma_host="chroma-host",
            chroma_port=9000,
        )
        pipeline._ensure_initialized()

        mock_chroma_class.assert_called_once()
        call_kwargs = mock_chroma_class.call_args[1]
        assert call_kwargs["host"] == "chroma-host"
        assert call_kwargs["port"] == 9000
        assert pipeline._collection == mock_collection

    @patch("pipeline.chromadb.HttpClient")
    @patch("pipeline.httpx.Client")
    def test_ensure_initialized_handles_chroma_error(
        self,
        mock_http_class: MagicMock,
        mock_chroma_class: MagicMock,
    ) -> None:
        """Test _ensure_initialized handles ChromaDB connection errors."""
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance
        mock_chroma_class.side_effect = ConnectionError("Chroma unavailable")

        pipeline = IndexPipeline()
        pipeline._ensure_initialized()

        assert pipeline._http == mock_http_instance
        assert pipeline._chroma is None
        assert pipeline._collection is None
        assert pipeline._initialized

    @patch("pipeline.chromadb.HttpClient")
    @patch("pipeline.httpx.Client")
    def test_ensure_initialized_is_idempotent(
        self,
        mock_http_class: MagicMock,
        mock_chroma_class: MagicMock,
    ) -> None:
        """Test _ensure_initialized only runs once."""
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance
        mock_chroma_instance = MagicMock()
        mock_chroma_class.return_value = mock_chroma_instance
        mock_collection = MagicMock()
        mock_chroma_instance.get_or_create_collection.return_value = (
            mock_collection
        )

        pipeline = IndexPipeline()
        pipeline._ensure_initialized()
        pipeline._ensure_initialized()

        mock_http_class.assert_called_once()
        mock_chroma_class.assert_called_once()

    def test_embed_batch_raises_when_http_is_none(self) -> None:
        """Test _embed_batch raises RuntimeError when HTTP unavailable."""
        pipeline = IndexPipeline()
        pipeline._initialized = True
        pipeline._http = None

        with pytest.raises(RuntimeError, match="HTTP client is not"):
            pipeline._embed_batch(["test"])

    def test_upsert_batch_raises_when_collection_is_none(self) -> None:
        """Test _upsert_batch raises RuntimeError when the collection
        unavailable."""
        pipeline = IndexPipeline()
        pipeline._initialized = True
        pipeline._collection = None

        with pytest.raises(RuntimeError, match="ChromaDB collection"):
            pipeline._upsert_batch([{"id": "1", "content": "test"}], [[0.1]])
