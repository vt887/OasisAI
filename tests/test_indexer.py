"""Tests for the oasis-indexer chunker module."""
import sys
import os
import tempfile
from pathlib import Path

import pytest

# Add the service to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "oasis-indexer"))

from chunker import CodeChunker, _make_id
from scanner import RepoScanner


class TestCodeChunker:
    def setup_method(self):
        self.chunker = CodeChunker(chunk_size=5, overlap=1)

    def _write_file(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "sample.py"
        f.write_text(content)
        return f

    def test_basic_chunking(self, tmp_path):
        lines = "\n".join(f"line{i}" for i in range(20))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(f, repo="testrepo", language="python")
        assert len(chunks) > 1
        assert all(c["repo"] == "testrepo" for c in chunks)
        assert all(c["language"] == "python" for c in chunks)

    def test_chunk_ids_unique(self, tmp_path):
        lines = "\n".join(f"x = {i}" for i in range(30))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        assert chunks == []

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.py"
        chunks = self.chunker.chunk_file(f, repo="r", language="python")
        assert chunks == []

    def test_chunk_metadata_fields(self, tmp_path):
        lines = "\n".join(f"line{i}" for i in range(10))
        f = self._write_file(tmp_path, lines)
        chunks = self.chunker.chunk_file(f, repo="repo1", language="javascript")
        first = chunks[0]
        assert "start_line" in first
        assert "end_line" in first
        assert "chunk_index" in first
        assert first["chunk_index"] == 0

    def test_invalid_overlap_raises(self):
        with pytest.raises(ValueError):
            CodeChunker(chunk_size=5, overlap=5)


class TestMakeId:
    def test_deterministic(self):
        id1 = _make_id("repo", "/path/to/file.py", 0)
        id2 = _make_id("repo", "/path/to/file.py", 0)
        assert id1 == id2

    def test_different_chunks_different_ids(self):
        id1 = _make_id("repo", "/path/to/file.py", 0)
        id2 = _make_id("repo", "/path/to/file.py", 1)
        assert id1 != id2


class TestRepoScanner:
    def test_scan_finds_python(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("def foo(): pass")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        paths = [str(p) for p, _ in results]
        langs = [lang for _, lang in results]
        assert all(lang == "python" for lang in langs)
        assert len(results) == 2

    def test_scan_skips_pycache(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("")
        (tmp_path / "main.py").write_text("x = 1")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        assert len(results) == 1

    def test_scan_multiple_languages(self, tmp_path):
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "index.js").write_text("console.log('hi')")
        (tmp_path / "main.go").write_text("package main")
        scanner = RepoScanner(str(tmp_path))
        results = scanner.scan()
        langs = {lang for _, lang in results}
        assert langs == {"python", "javascript", "go"}

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            RepoScanner("/nonexistent/path/that/does/not/exist")
