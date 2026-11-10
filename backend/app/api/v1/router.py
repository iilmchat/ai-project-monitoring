"""API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    activity,
    admin,
    ai_providers,
    auth,
    automation,
    dashboard,
    health,
    metrics,
    repositories,
    sast,
    scan,
    search,
    settings,
    team,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(auth.router)
api_router.include_router(scan.router)
api_router.include_router(settings.router)
api_router.include_router(ai_providers.router)
api_router.include_router(repositories.router)
api_router.include_router(sast.router)
api_router.include_router(automation.router)
api_router.include_router(search.router)
api_router.include_router(dashboard.router)
api_router.include_router(activity.router)
api_router.include_router(webhooks.router)
api_router.include_router(admin.router)
api_router.include_router(team.router)

__all__ = ["api_router"]
