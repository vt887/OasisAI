from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, max_size: int = 1024, ttl_seconds: int = 30) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        now = time.time()
        with self._lock:
            value = self._store.get(key)
            if value is None:
                return None
            expires_at, item = value
            if expires_at < now:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return item

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl_seconds, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)
