"""Services package for OasisAI.

This package groups the per-service Python packages under
the repository's `services/` directory so imports are
unambiguous (e.g. `from services.llm.ollama_client ...`).
"""

__all__ = ["agent", "gateway", "graph", "indexer", "llm"]
