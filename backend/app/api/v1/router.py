"""API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import dashboard, health, metrics, repositories, scan, webhooks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(scan.router)
api_router.include_router(repositories.router)
api_router.include_router(dashboard.router)
api_router.include_router(webhooks.router)

__all__ = ["api_router"]
