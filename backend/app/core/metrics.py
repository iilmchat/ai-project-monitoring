"""Prometheus metrics (S8-001, S8-002)."""

from __future__ import annotations

from collections.abc import Mapping

from prometheus_client import Counter, Gauge, Histogram

FETCH_DURATION = Histogram(
    "iiruchating_fetch_duration_seconds",
    "Duration of git fetch per repository",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

STATUS_DURATION = Histogram(
    "iiruchating_status_duration_seconds",
    "Duration of collecting a repository status",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

REPOSITORIES_TOTAL = Gauge(
    "iiruchating_repositories_total",
    "Current number of repositories by canonical state",
    labelnames=("state",),
)

SCAN_DURATION = Gauge(
    "iiruchating_scan_duration_seconds",
    "Duration of the last full discovery scan",
)

MIRROR_STATUS_TOTAL = Gauge(
    "iiruchating_mirror_status_total",
    "Current number of repositories by mirror status",
    labelnames=("status",),
)

MIRROR_CHECK_DURATION = Histogram(
    "iiruchating_mirror_check_duration_seconds",
    "Duration of a GitHub <-> GitFlic mirror check",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

AI_CACHE_HITS = Counter(
    "iiruchating_ai_cache_hits_total",
    "AI cache hits by feature",
    labelnames=("feature",),
)

AI_CACHE_MISSES = Counter(
    "iiruchating_ai_cache_misses_total",
    "AI cache misses by feature",
    labelnames=("feature",),
)

AI_LLM_CALLS = Counter(
    "iiruchating_ai_llm_calls_total",
    "LLM calls by feature, provider and status",
    labelnames=("feature", "provider", "status"),
)


def observe_ai_cache(feature: str, *, hit: bool) -> None:
    counter = AI_CACHE_HITS if hit else AI_CACHE_MISSES
    counter.labels(feature=feature).inc()


def observe_llm_call(feature: str, provider: str, status: str) -> None:
    AI_LLM_CALLS.labels(
        feature=feature,
        provider=provider,
        status=status,
    ).inc()


def observe_fetch_duration(seconds: float) -> None:
    FETCH_DURATION.observe(max(seconds, 0.0))


def observe_status_duration(seconds: float) -> None:
    STATUS_DURATION.observe(max(seconds, 0.0))


def observe_scan_duration(seconds: float) -> None:
    SCAN_DURATION.set(max(seconds, 0.0))


def set_repository_state_counts(counts: Mapping[str, int]) -> None:
    """Replace the state gauge with the counts from the current DB snapshot."""
    REPOSITORIES_TOTAL.clear()
    for state, count in counts.items():
        REPOSITORIES_TOTAL.labels(state=state).set(count)


def observe_mirror_check_duration(seconds: float) -> None:
    MIRROR_CHECK_DURATION.observe(max(seconds, 0.0))


def set_mirror_status_counts(counts: Mapping[str, int]) -> None:
    """Replace the mirror-status gauge with the current DB snapshot."""
    MIRROR_STATUS_TOTAL.clear()
    for status, count in counts.items():
        MIRROR_STATUS_TOTAL.labels(status=status).set(count)


__all__ = [
    "AI_CACHE_HITS",
    "AI_CACHE_MISSES",
    "AI_LLM_CALLS",
    "FETCH_DURATION",
    "MIRROR_CHECK_DURATION",
    "MIRROR_STATUS_TOTAL",
    "REPOSITORIES_TOTAL",
    "SCAN_DURATION",
    "STATUS_DURATION",
    "observe_ai_cache",
    "observe_fetch_duration",
    "observe_llm_call",
    "observe_mirror_check_duration",
    "observe_scan_duration",
    "observe_status_duration",
    "set_mirror_status_counts",
    "set_repository_state_counts",
]
