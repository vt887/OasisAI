"""Pydantic models shared across all OasisAI services."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"
    UNKNOWN = "unknown"


class NodeKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    IMPORT = "import"


# ---------------------------------------------------------------------------
# Indexer / Chunk models
# ---------------------------------------------------------------------------


class ChunkMetadata(BaseModel):
    repo: str = Field(..., description="Repository name or path")
    file_path: str = Field(
        ..., description="Relative file path within the repo"
    )
    module: str | None = Field(
        None, description="Python module path or dotted module name"
    )
    language: Language = Language.UNKNOWN
    start_line: int = Field(0, ge=0)
    end_line: int = Field(0, ge=0)
    chunk_index: int = Field(0, ge=0)
    token_count: int = Field(0, ge=0, description="Estimated token count")
    embedding_id: str | None = Field(
        None, description="ID of embedding/vector in vector DB"
    )


class CodeChunk(BaseModel):
    id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Source code text")
    metadata: ChunkMetadata
    embedding: list[float] | None = Field(
        None, description="Vector embedding (set after encoding)"
    )
    # Symbol-aware metadata: list of symbols defined or encompassed by this
    # chunk (functions, classes, methods)
    symbols: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "List of symbol dicts with keys: name, kind, start_line, "
            "end_line, qualified_name"
        ),
    )


class IndexRequest(BaseModel):
    repo_path: str = Field(
        ..., description="Absolute path to the git repository"
    )
    repo_name: str = Field(..., description="Logical name for the repository")


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int
    status: str = "ok"


# ---------------------------------------------------------------------------
# Search models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    repo: str | None = Field(
        None, description="Limit search to a specific repo"
    )
    top_k: int = Field(5, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    metadata: ChunkMetadata
    score: float = Field(
        ..., description="Similarity score (higher is better)"
    )
    repo: str | None = None
    symbol: str | None = None


# ---------------------------------------------------------------------------
# Ask / Agent models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    repo: str | None = None
    top_k: int = Field(5, ge=1, le=50)


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult] = []


# ---------------------------------------------------------------------------
# Refactor models
# ---------------------------------------------------------------------------


class RefactorRequest(BaseModel):
    instruction: str = Field(
        ..., min_length=1, description="Natural language refactor goal"
    )
    repo: str | None = None
    target_file: str | None = Field(
        None, description="Specific file to refactor"
    )
    top_k: int = Field(5, ge=1, le=50)


class RefactorResponse(BaseModel):
    plan: str = Field(
        ..., description="Textual description of the refactor plan"
    )
    patches: list[str] = Field(
        default_factory=list, description="Unified diff patches (read-only)"
    )
    sources: list[SearchResult] = []


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    id: str = Field(
        ..., description="Unique node ID (e.g., module::ClassName)"
    )
    kind: NodeKind
    name: str
    qualified_name: str | None = Field(
        None, description="Fully-qualified name (repo.module:Class.method)"
    )
    file_path: str
    start_line: int = 0
    end_line: int = 0
    repo: str = ""
    ast_hash: str | None = Field(
        None, description="Short hash of AST for change detection"
    )
    exports: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relation: str = Field(
        ..., description="e.g. 'calls', 'imports', 'inherits'"
    )


class CodeGraph(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


# ---------------------------------------------------------------------------
# LLM models
# ---------------------------------------------------------------------------


class EmbeddingRequest(BaseModel):
    text: str
    model: str = "nomic-embed-text"


class EmbeddingResponse(BaseModel):
    embedding: list[float]
    model: str


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "codellama"
    system: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    text: str
    model: str
    done: bool = True
