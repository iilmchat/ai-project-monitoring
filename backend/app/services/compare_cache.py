"""In-memory TTL cache for repository compare results (KI-003)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.git.pygit2_backend import CompareResult

CompareKey = tuple[int, str, str]


@dataclass(frozen=True, slots=True)
class _Entry:
    stored_at: float
    result: CompareResult


class CompareCache:
    """Cache ``CompareResult`` by ``(repository_id, base, head)`` for a TTL."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(ttl_seconds, 0)
        self._items: dict[CompareKey, _Entry] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def get(self, repository_id: int, base: str, head: str) -> CompareResult | None:
        key: CompareKey = (repository_id, base, head)
        entry = self._items.get(key)
        if entry is None:
            return None
        if self._ttl <= 0 or (time.monotonic() - entry.stored_at) >= self._ttl:
            self._items.pop(key, None)
            return None
        return entry.result

    def set(self, repository_id: int, base: str, head: str, result: CompareResult) -> None:
        key: CompareKey = (repository_id, base, head)
        self._items[key] = _Entry(stored_at=time.monotonic(), result=result)

    def invalidate(self, repository_id: int | None = None) -> None:
        if repository_id is None:
            self._items.clear()
            return
        for key in [key for key in self._items if key[0] == repository_id]:
            self._items.pop(key, None)


__all__ = ["CompareCache", "CompareKey"]
