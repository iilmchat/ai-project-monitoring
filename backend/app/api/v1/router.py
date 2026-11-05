"""API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, repositories, scan

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(scan.router)
api_router.include_router(repositories.router)

__all__ = ["api_router"]
