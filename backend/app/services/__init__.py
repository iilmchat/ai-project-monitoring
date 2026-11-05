"""Business logic services."""

from __future__ import annotations

from app.services.action_service import ActionService
from app.services.bulk_service import BulkService
from app.services.discovery_service import DiscoveryService, ScanResult
from app.services.mirror_scheduler import MirrorScheduler
from app.services.mirror_service import MirrorService, MirrorSnapshot, classify_mirror_status
from app.services.notification_service import NotificationService
from app.services.recommendation_service import Recommendation, generate_recommendations
from app.services.remote_service import RemoteFetchResult, RemoteService
from app.services.status_service import (
    StatusCache,
    StatusService,
    StatusSnapshot,
    classify_state,
)

__all__ = [
    "ActionService",
    "BulkService",
    "DiscoveryService",
    "MirrorScheduler",
    "MirrorService",
    "MirrorSnapshot",
    "NotificationService",
    "Recommendation",
    "RemoteFetchResult",
    "RemoteService",
    "ScanResult",
    "StatusCache",
    "StatusService",
    "StatusSnapshot",
    "classify_mirror_status",
    "classify_state",
    "generate_recommendations",
]
