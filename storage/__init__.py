"""Storage package for OasisAI.

This package exposes storage-related subpackages such as `storage.chroma`.
Adding this file prevents mypy and Python from treating `storage/chroma`
as a top-level package named `chroma` which can result in duplicate
module-name errors.
"""

# Package marker
__all__ = ["chroma"]
