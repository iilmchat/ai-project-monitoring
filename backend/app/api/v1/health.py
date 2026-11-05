"""Health check endpoint (SPEC §3.1, S8-004)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])

# Token-based checks arrive in Sprint 9 (mirror); v0.1.0 reports stubs.
PROVIDERS: dict[str, str] = {"github": "not_configured", "gitflic": "not_configured"}


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    settings: Settings = request.app.state.settings
    git_version: str | None = getattr(request.app.state, "git_version", None)

    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.app_version,
        git_version=git_version,
        scan_roots=settings.scan_root_paths,
        db_ok=db_ok,
        providers=PROVIDERS,
    )
