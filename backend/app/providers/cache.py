"""Provider-level query helpers."""

from __future__ import annotations

from typing import Any


class TTLCache:
    """Tiny in-memory TTL cache for provider responses (S13-002)."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        import time

        self._time = time
        self._ttl = max(ttl_seconds, 0)
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._ttl <= 0 or (self._time.monotonic() - stored_at) >= self._ttl:
            self._items.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._items[key] = (self._time.monotonic(), value)

    def clear(self) -> None:
        self._items.clear()


__all__ = ["TTLCache"]
