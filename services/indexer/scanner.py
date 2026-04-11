"""Repository file scanner.

Walk a local repository tree and return supported source files.

The scanner yields absolute paths paired with a language label for each
supported source file found under the repository root. Certain
directories (build artifacts, virtualenvs, etc.) are skipped to avoid
noise.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Map file extensions → language labels.
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
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}

# Directory names to skip while walking the tree.
_SKIP_DIRS: set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
}


def _is_skipped_dir(name: str) -> bool:
    """Return True if the directory name should be skipped.

    Hidden directories (starting with a dot) and entries in
    ``_SKIP_DIRS`` are ignored.
    """
    return name in _SKIP_DIRS or name.startswith(".")


def _language_for_suffix(suffix: str) -> str | None:
    """Return the language label for a file suffix if supported.

    The suffix must include the leading dot and be lower-cased.
    """
    return _EXT_LANG.get(suffix)


class RepoScanner:
    """Recursively scan a repository and return (path, language) tuples.

    Args:
        repo_path: Path to the repository root. The path must exist and
            be a directory.
    """

    def __init__(self, repo_path: str) -> None:
        self._root = Path(repo_path).resolve()
        if not self._root.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    def scan(self) -> list[tuple[Path, str]]:
        """Return a list of (absolute_path, language) for supported files.

        The implementation uses ``os.walk`` and prunes directories in
        place to avoid descending into ignored folders.
        """
        results: list[tuple[Path, str]] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            # Prune ignored directories so os.walk won't descend into them.
            dirnames[:] = [d for d in dirnames if not _is_skipped_dir(d)]
            for fname in filenames:
                suffix = Path(fname).suffix.lower()
                lang = _language_for_suffix(suffix)
                if not lang:
                    continue
                full_path = (Path(dirpath) / fname).resolve()
                # Guard against symlink escapes outside of the repo root.
                try:
                    full_path.relative_to(self._root)
                except ValueError:
                    logger.warning("Skipping file outside root: %s", full_path)
                    continue
                results.append((full_path, lang))

        logger.info(
            "Scanned %s: found %d source files", self._root, len(results)
        )
        return results
