"""Code chunker: split source files into overlapping text windows.

This module provides a small utility to split source files into
fixed-size, overlapping line windows suitable for indexing.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Iterator

from shared.config import settings

logger = logging.getLogger(__name__)


class CodeChunker:
    """Split a source file into fixed-size, overlapping line-window
    chunks.

    Args:
        chunk_size: Number of lines per chunk. Defaults to
            ``settings.chunk_size``.
        overlap: Number of overlapping lines between consecutive
            chunks. Defaults to ``settings.chunk_overlap``.
    """

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        overlap: int = settings.chunk_overlap,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk_file(
        self,
        file_path: Path | str,
        repo: str,
        language: str,
    ) -> list[dict[str, Any]]:
        """Read *file_path* and return chunk dicts for indexing.

        The returned list contains dictionaries with the following keys:
        ``id``, ``content``, ``repo``, ``file_path``, ``language``,
        ``start_line``, ``end_line`` and ``chunk_index``.

        Args:
            file_path: Path or string path to the source file.
            repo: Repository name to include in chunk metadata.
            language: Language label for the file.

        Returns:
            A list of chunk metadata dictionaries. Empty on read
            failures or when the file has no content.
        """
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return []
        lines = text.splitlines(keepends=True)
        if not lines:
            return []

        # For Python files prefer symbol-aware chunking (functions/classes).
        if language == "python":
            try:
                return list(
                    self._chunk_python(path, repo, language, lines, text)
                )
            except Exception:
                logger.exception("symbol-aware chunking failed for %s", path)

        # Fallback to window-based chunks for other languages or on error.
        return list(self.iter_chunks(path, repo, language, lines))

    def iter_chunks(
        self,
        path: Path,
        repo: str,
        language: str,
        lines: list[str],
    ) -> Iterator[dict[str, Any]]:
        """Yield chunk dictionaries for *lines*.

        This method is the core chunking logic and is separated from
        ``chunk_file`` so it can be reused or tested independently.
        """
        step = max(1, self._chunk_size - self._overlap)
        for chunk_index, start in enumerate(range(0, len(lines), step)):
            end = min(start + self._chunk_size, len(lines))
            content = "".join(lines[start:end])
            if not content.strip():
                # Skip empty/whitespace-only chunks
                continue

            yield {
                "id": _make_id(repo, str(path), chunk_index),
                "content": content,
                "repo": repo,
                "file_path": str(path),
                "language": language,
                "start_line": start,
                "end_line": end - 1,
                "chunk_index": chunk_index,
            }

    def _chunk_python(
        self,
        path: Path,
        repo: str,
        language: str,
        lines: list[str],
        full_text: str,
    ) -> Iterator[dict[str, Any]]:
        """Yield symbol-aware chunks for Python files: one chunk per
        top-level function or class (including methods as part of class
        body). If no symbols are found, yield windowed chunks instead.
        """
        import ast

        module_name = path.stem
        tree = ast.parse(full_text)
        symbols: list[tuple[int, int, str, str]] = []  # start, end, kind, name
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None) or start
                if isinstance(start, int) and isinstance(end, int):
                    symbols.append(
                        (start - 1, end, "function", str(node.name))
                    )
            elif isinstance(node, ast.ClassDef):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None) or start
                if isinstance(start, int) and isinstance(end, int):
                    symbols.append((start - 1, end, "class", str(node.name)))

        if not symbols:
            # No top-level symbols: fallback to window chunks
            yield from self.iter_chunks(path, repo, language, lines)
            return

        # Sort symbols by start line
        symbols.sort(key=lambda x: x[0])
        chunk_index = 0
        for start, end, kind, name in symbols:
            content = "".join(lines[start:end])
            token_count = max(10, int(len(content) / 50))
            yield {
                "id": _make_id(repo, str(path), f"sym-{start}-{end}-{name}"),
                "content": content,
                "repo": repo,
                "file_path": str(path),
                "module": module_name,
                "language": language,
                "start_line": start + 1,
                "end_line": end,
                "chunk_index": chunk_index,
                "symbols": [
                    {
                        "name": name,
                        "kind": kind,
                        "start_line": start + 1,
                        "end_line": end,
                        "qualified_name": f"{module_name}.{name}",
                    }
                ],
                "token_count": token_count,
            }
            chunk_index += 1


def _make_id(repo: str, file_path: str, chunk_index: int | str) -> str:
    """Return a deterministic id for a chunk.

    The id is an MD5 hex digest of the repo, file path and chunk
    index. This is sufficient for identification in a non-security
    context.
    """
    raw = f"{repo}::{file_path}::{chunk_index}"
    # Deterministic non-cryptographic id for chunk identification.
    hexdigest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return hexdigest  # noqa: S303 (non-security use)
