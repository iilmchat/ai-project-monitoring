"""Remote operations: fetch with timeout and graceful error handling (S3-001)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.core.metrics import observe_fetch_duration
from app.git.command_backend import fetch_all, get_remote_url

logger = structlog.get_logger(__name__)

REMOTE_OK = "ok"
REMOTE_UNAVAILABLE = "unavailable"
REMOTE_STALE = "stale"


@dataclass(frozen=True, slots=True)
class RemoteFetchResult:
    """Result of a fetch attempt; failures are data, not exceptions."""

    ok: bool
    duration_ms: float
    error: str | None = None
    timed_out: bool = False


class RemoteService:
    """Run ``git fetch --all --prune`` without blocking the event loop."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout = timeout_seconds

    @property
    def timeout_seconds(self) -> float:
        return self._timeout

    def set_timeout(self, seconds: float) -> None:
        self._timeout = max(float(seconds), 1.0)

    async def fetch(self, repository_path: str | Path) -> RemoteFetchResult:
        result = await asyncio.to_thread(fetch_all, repository_path, self._timeout)
        observe_fetch_duration(result.duration_ms / 1000)
        if result.ok:
            logger.info(
                "fetch_completed",
                path=str(repository_path),
                duration_ms=result.duration_ms,
            )
            return RemoteFetchResult(ok=True, duration_ms=result.duration_ms)

        remote_url = await asyncio.to_thread(get_remote_url, repository_path)
        if result.timed_out:
            logger.warning(
                "fetch_timed_out",
                path=str(repository_path),
                remote_url=remote_url,
                timeout_seconds=self._timeout,
                message=(
                    f"Fetch timed out after {self._timeout:g}s. "
                    "Consider increasing FETCH_TIMEOUT"
                ),
            )
        else:
            logger.warning(
                "fetch_failed",
                path=str(repository_path),
                remote_url=remote_url,
                duration_ms=result.duration_ms,
                error=result.error,
            )
        return RemoteFetchResult(
            ok=False,
            duration_ms=result.duration_ms,
            error=result.error,
            timed_out=result.timed_out,
        )


__all__ = ["REMOTE_OK", "REMOTE_STALE", "REMOTE_UNAVAILABLE", "RemoteFetchResult", "RemoteService"]
