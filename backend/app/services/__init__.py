"""Business logic services."""

from __future__ import annotations

from app.services.discovery_service import DiscoveryService, ScanResult
from app.services.recommendation_service import Recommendation, generate_recommendations
from app.services.remote_service import RemoteFetchResult, RemoteService
from app.services.status_service import (
    StatusCache,
    StatusService,
    StatusSnapshot,
    classify_state,
)

__all__ = [
    "DiscoveryService",
    "Recommendation",
    "RemoteFetchResult",
    "RemoteService",
    "ScanResult",
    "StatusCache",
    "StatusService",
    "StatusSnapshot",
    "classify_state",
    "generate_recommendations",
]
