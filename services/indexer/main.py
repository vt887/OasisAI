from __future__ import annotations

import argparse
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pipeline import IndexPipeline
from pydantic import BaseModel

from shared.observability.logging import (
    configure_logging,
    request_logging_middleware,
)

logger = configure_logging("oasis-indexer")

app = FastAPI(title="OasisAI Indexer", version="0.2.0")
pipeline = IndexPipeline()


@app.middleware("http")
async def log_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Any]]
) -> Any:
    return await request_logging_middleware(request, call_next, logger)


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "indexer unhandled", extra={"operation": request.url.path}
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Unexpected server error",
        },
    )


class IndexRequest(BaseModel):
    repo_path: str
    repo_name: str


class IndexResponse(BaseModel):
    repo_name: str
    chunks_indexed: int
    status: str = "ok"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "oasis-indexer"}


@app.post("/index", response_model=IndexResponse)
async def index_repo(req: IndexRequest) -> IndexResponse:
    start = time.perf_counter()
    try:
        count = pipeline.index_repo(
            repo_path=req.repo_path, repo_name=req.repo_name
        )
        logger.info(
            "index complete",
            extra={
                "operation": "index",
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return IndexResponse(repo_name=req.repo_name, chunks_indexed=count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("index failed", extra={"operation": "index"})
        raise HTTPException(status_code=500, detail="Indexing failed") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Oasis Indexer CLI")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--name", default="local-repo")
    args = parser.parse_args()
    count = pipeline.index_repo(args.repo, args.name)
    print(f"Indexed {count} chunks for {args.name}")


if __name__ == "__main__":
    main()
