"""SAST API (v1.3.0, Sprint 59)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.sast import SastReport
from app.services.sast_service import SastService

router = APIRouter(tags=["sast"])


def _service(request: Request) -> SastService:
    service: SastService = request.app.state.sast_service
    return service


@router.get(
    "/repositories/{repository_id}/sast",
    response_model=SastReport,
)
async def repository_sast(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
    tools: Annotated[
        Literal["all", "bandit", "semgrep", "eslint"], Query()
    ] = "all",
    min_severity: Annotated[
        Literal["critical", "high", "medium", "low", "all"], Query()
    ] = "all",
) -> SastReport:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="repository_not_found",
        )
    return await _service(request).get_report(
        repository.id,
        repository.path,
        refresh=refresh,
        tools=tools,
        min_severity=min_severity,
    )


__all__ = ["router"]
