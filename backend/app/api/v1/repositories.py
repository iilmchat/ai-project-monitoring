"""Repository endpoints: listing, status, refresh, compare and log."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.git.pygit2_backend import (
    GitStatusError,
    compare_refs,
    read_commits,
    read_local_status,
)
from app.models.entities import Repository
from app.schemas.repository import (
    CommitInfoResponse,
    CompareResponse,
    RefreshRequest,
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


@router.post("/repositories/{repository_id}/track", response_model=RepositoryRead)
async def track_repository(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    repository.tracked = True
    await session.commit()
    await session.refresh(repository)
    return RepositoryRead.model_validate(repository)


@router.post("/repositories/{repository_id}/untrack", response_model=RepositoryRead)
async def untrack_repository(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    repository.tracked = False
    await session.commit()
    await session.refresh(repository)
    return RepositoryRead.model_validate(repository)


@router.get("/repositories/{repository_id}/status", response_model=RepositoryStatusResponse)
async def get_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    fetch: Annotated[bool, Query()] = True,
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).get_status(
        session, repository, use_cache=True, fetch=fetch
    )
    return RepositoryStatusResponse.model_validate(snapshot)


@router.post("/repositories/{repository_id}/refresh", response_model=RepositoryStatusResponse)
async def refresh_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: RefreshRequest | None = None,
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    should_fetch = payload.fetch if payload is not None else True
    snapshot = await _status_service(request).refresh(session, repository, fetch=should_fetch)
    return RepositoryStatusResponse.model_validate(snapshot)


@router.get("/repositories/{repository_id}/compare", response_model=CompareResponse)
async def compare_repository(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    base: Annotated[str | None, Query()] = None,
    head: Annotated[str | None, Query()] = None,
) -> CompareResponse:
    repository = await _get_repository(session, repository_id)

    resolved_base = base
    if resolved_base is None:
        try:
            local = await asyncio.to_thread(read_local_status, repository.path)
        except GitStatusError:
            return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])
        resolved_base = local.upstream

    if resolved_base is None:
        return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])

    try:
        result = await asyncio.to_thread(
            compare_refs,
            repository.path,
            resolved_base,
            head or "HEAD",
            10,
        )
    except GitStatusError:
        return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])

    return CompareResponse.model_validate(result)


@router.get("/repositories/{repository_id}/log", response_model=list[CommitInfoResponse])
async def repository_log(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[CommitInfoResponse]:
    repository = await _get_repository(session, repository_id)
    try:
        commits = await asyncio.to_thread(read_commits, repository.path, "HEAD", limit)
    except GitStatusError:
        return []
    return [CommitInfoResponse.model_validate(commit) for commit in commits]
