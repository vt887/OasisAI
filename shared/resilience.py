from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def async_retry(
    operation: Callable[[], Awaitable[T]],
    retries: int = 3,
    backoff_seconds: float = 0.5,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            delay = backoff_seconds * (2**attempt) + random.uniform(0, 0.1)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
