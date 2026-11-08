"""Smart AI cache keys and single-flight locks (S43-003)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.db.base import utcnow

MAX_CACHE_KEY_LENGTH = 255
_LOCKS: dict[str, asyncio.Lock] = {}


def state_hash(state: Any) -> str:
    """Return a stable SHA-256 over a canonical JSON representation."""
    canonical = json.dumps(
        state,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_cache_key(
    feature: str,
    scope: str,
    state: Any,
    model: str | None,
    prompt_version: str,
) -> str:
    """Build ``<feature>:<scope>:<state_hash>:<model>:<prompt_version>``.

    If the model name makes the key longer than the DB column, it is replaced
    with a short digest. State hashes and prompt versions stay intact so a
    prompt bump always invalidates old rows.
    """
    digest = state_hash(state)
    model_part = model or "unknown"
    key = f"{feature}:{scope}:{digest}:{model_part}:{prompt_version}"
    if len(key) > MAX_CACHE_KEY_LENGTH:
        short_model = hashlib.sha256(model_part.encode("utf-8")).hexdigest()[:16]
        key = f"{feature}:{scope}:{digest}:{short_model}:{prompt_version}"
    return key


def cache_lock(key: str) -> asyncio.Lock:
    """Return a process-local lock for single-flight generation."""
    return _LOCKS.setdefault(key, asyncio.Lock())


def cache_is_fresh(checked_at: datetime, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0:
        return False
    value = checked_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    age = (utcnow() - value).total_seconds()
    return 0 <= age < ttl_seconds


__all__ = [
    "MAX_CACHE_KEY_LENGTH",
    "build_cache_key",
    "cache_is_fresh",
    "cache_lock",
    "state_hash",
]
