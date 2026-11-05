"""Repository endpoints: listing and local status (SPEC §3.2, §3.4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.repository import (
    RepositoryListResponse,
    RepositoryRead,
    RepositoryStatusResponse,
)
from app.services.status_service import StatusService

router = APIRouter(tags=["repositories"])


def _status_service(request: Request) -> StatusService:
    service: StatusService = request.app.state.status_service
    return service


async def _get_repository(session: AsyncSession, repository_id: int) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"repository {repository_id} not found",
        )
    return repository


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    session: Annotated[AsyncSession, Depends(get_session)],
    tracked: Annotated[bool | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> RepositoryListResponse:
    filters = []
    if tracked is not None:
        filters.append(Repository.tracked.is_(tracked))

    total = await session.scalar(select(func.count()).select_from(Repository).where(*filters))
    result = await session.scalars(
        select(Repository).where(*filters).order_by(Repository.path).offset(skip).limit(limit)
    )
    items = [RepositoryRead.model_validate(item) for item in result.all()]

    return RepositoryListResponse(
        items=items,
        total=total or 0,
        skip=skip,
        limit=limit,
    )


@router.get("/repositories/{repository_id}/status", response_model=RepositoryStatusResponse)
async def get_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).get_status(session, repository, use_cache=True)
    return RepositoryStatusResponse.model_validate(snapshot)


@router.post("/repositories/{repository_id}/refresh", response_model=RepositoryStatusResponse)
async def refresh_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).refresh(session, repository)
    return RepositoryStatusResponse.model_validate(snapshot)
