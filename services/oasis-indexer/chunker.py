"""Code chunker: splits source files into overlapping text windows."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 60   # lines per chunk
_DEFAULT_OVERLAP = 10      # lines of overlap between consecutive chunks


class CodeChunker:
    """Split a source file into fixed-size, overlapping line-window chunks."""

    def __init__(
        self,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk_file(
        self,
        file_path: Path,
        repo: str,
        language: str,
    ) -> list[dict]:
        """Read *file_path* and return a list of chunk dicts ready for indexing.

        Each dict has:
          id, content, repo, file_path, language, start_line, end_line, chunk_index
        """
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return []

        lines = text.splitlines(keepends=True)
        if not lines:
            return []

        chunks: list[dict] = []
        step = self._chunk_size - self._overlap
        chunk_index = 0

        for start in range(0, len(lines), step):
            end = min(start + self._chunk_size, len(lines))
            content = "".join(lines[start:end])
            if not content.strip():
                continue

            chunk_id = _make_id(repo, str(file_path), chunk_index)
            chunks.append(
                {
                    "id": chunk_id,
                    "content": content,
                    "repo": repo,
                    "file_path": str(file_path),
                    "language": language,
                    "start_line": start,
                    "end_line": end - 1,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
            if end >= len(lines):
                break

        logger.debug("Chunked %s → %d chunks", file_path, len(chunks))
        return chunks


def _make_id(repo: str, file_path: str, chunk_index: int) -> str:
    raw = f"{repo}::{file_path}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S303 (non-security use)
