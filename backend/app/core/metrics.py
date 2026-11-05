"""Prometheus metrics (S8-001, S8-002)."""

from __future__ import annotations

from collections.abc import Mapping

from prometheus_client import Gauge, Histogram

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


__all__ = [
    "FETCH_DURATION",
    "REPOSITORIES_TOTAL",
    "SCAN_DURATION",
    "STATUS_DURATION",
    "observe_fetch_duration",
    "observe_scan_duration",
    "observe_status_duration",
    "set_repository_state_counts",
]
