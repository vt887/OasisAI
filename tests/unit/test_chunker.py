"""Unit tests for symbol-aware chunker."""

from __future__ import annotations

from pathlib import Path

from services.indexer.chunker import CodeChunker


def test_chunk_python_symbols() -> None:
    repo = "sample-app"
    path = Path("repos/sample-app/main.py")
    chunker = CodeChunker()
    chunks = chunker.chunk_file(path, repo=repo, language="python")
    names = []
    for c in chunks:
        syms = c.get("symbols") or []
        for s in syms:
            names.append(s.get("name"))

    # Expect top-level functions from sample-app/main.py
    assert "process_user_data" in names
    assert "perform_calculation" in names
    assert "main" in names
