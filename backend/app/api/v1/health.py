"""Health check endpoint (SPEC §3.1, S1-005)."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


def _read_git_version() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    settings: Settings = request.app.state.settings
    git_version = await asyncio.to_thread(_read_git_version)

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
    )
