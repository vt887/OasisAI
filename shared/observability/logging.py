from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": getattr(record, "service", "oasis-service"),
            "request_id": getattr(record, "request_id", request_id_var.get()),
            "operation": getattr(record, "operation", "-"),
            "duration_ms": getattr(record, "duration_ms", None),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


class ContextAdapter(logging.LoggerAdapter):
    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("service", self.extra.get("service"))
        extra.setdefault("request_id", request_id_var.get())
        return msg, kwargs


def configure_logging(
    service_name: str, level: str = "INFO"
) -> ContextAdapter:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(JsonFormatter())
    return ContextAdapter(
        logging.getLogger(service_name), {"service": service_name}
    )


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Any]],
    logger: ContextAdapter,
) -> Any:
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = rid
        logger.info(
            f"{request.method} {request.url.path}",
            extra={"operation": request.url.path, "duration_ms": duration_ms},
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            f"Unhandled exception {request.method} {request.url.path}",
            extra={"operation": request.url.path, "duration_ms": duration_ms},
        )
        raise
    finally:
        request_id_var.reset(token)
