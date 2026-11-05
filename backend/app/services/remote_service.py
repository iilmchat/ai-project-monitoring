"""Remote operations: fetch with timeout and graceful error handling (S3-001)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.git.command_backend import fetch_all

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

    async def fetch(self, repository_path: str | Path) -> RemoteFetchResult:
        result = await asyncio.to_thread(fetch_all, repository_path, self._timeout)
        if result.ok:
            logger.info(
                "fetch_completed",
                path=str(repository_path),
                duration_ms=result.duration_ms,
            )
            return RemoteFetchResult(ok=True, duration_ms=result.duration_ms)

        if result.timed_out:
            logger.warning(
                "fetch_timed_out",
                path=str(repository_path),
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
