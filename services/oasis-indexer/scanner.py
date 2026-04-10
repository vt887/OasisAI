"""Repository file scanner.

Walks a local git repository and yields source-code file paths, filtering
by supported languages.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Map file extensions → Language labels
_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
}

# Directories to always skip
_SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
}


class RepoScanner:
    """Recursively scan a repository directory and yield (path, language) tuples."""

    def __init__(self, repo_path: str) -> None:
        self._root = Path(repo_path).resolve()
        if not self._root.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    def scan(self) -> list[tuple[Path, str]]:
        """Return a list of (absolute_path, language) for every supported source file."""
        results: list[tuple[Path, str]] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            # Prune ignored directories in-place so os.walk won't descend
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                suffix = Path(fname).suffix.lower()
                lang = _EXT_LANG.get(suffix)
                if lang:
                    full_path = Path(dirpath) / fname
                    results.append((full_path, lang))
        logger.info("Scanned %s: found %d source files", self._root, len(results))
        return results
