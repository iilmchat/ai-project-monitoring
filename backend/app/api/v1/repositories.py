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
from app.models.entities import ActionLog, Repository
from app.schemas.action import ActionLogResponse, ActionRequest
from app.schemas.mirror import (
    MirrorCandidatesResponse,
    MirrorPolicyUpdate,
    MirrorStatusResponse,
)
from app.schemas.recommendation import RecommendationResponse
from app.schemas.repository import (
    CommitInfoResponse,
    CompareResponse,
    RefreshRequest,
    RepositoryListResponse,
    RepositoryRead,
    RepositoryStatusResponse,
)
from app.services.action_service import (
    ActionNotAllowedError,
    ActionService,
    ConfirmationRequiredError,
    UnknownActionError,
)
from app.services.compare_cache import CompareCache
from app.services.mirror_service import MirrorService
from app.services.recommendation_service import generate_recommendations
from app.services.status_service import StatusService

router = APIRouter(tags=["repositories"])


def _status_service(request: Request) -> StatusService:
    service: StatusService = request.app.state.status_service
    return service


def _compare_cache(request: Request) -> CompareCache:
    cache: CompareCache = request.app.state.compare_cache
    return cache


def _mirror_service(request: Request) -> MirrorService:
    service: MirrorService = request.app.state.mirror_service
    return service


def _action_service(request: Request) -> ActionService:
    service: ActionService = request.app.state.action_service
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
    _compare_cache(request).invalidate(repository_id)
    return RepositoryStatusResponse.model_validate(snapshot)


@router.get(
    "/repositories/{repository_id}/recommendations",
    response_model=list[RecommendationResponse],
)
async def repository_recommendations(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RecommendationResponse]:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).get_status(
        session, repository, use_cache=True, fetch=False
    )
    status_response = RepositoryStatusResponse.model_validate(snapshot)
    return [
        RecommendationResponse.model_validate(item)
        for item in generate_recommendations(status_response)
    ]


@router.get("/repositories/{repository_id}/compare", response_model=CompareResponse)
async def compare_repository(
    repository_id: int,
    request: Request,
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

    resolved_head = head or "HEAD"
    cache = _compare_cache(request)
    cached = cache.get(repository.id, resolved_base, resolved_head)
    if cached is not None:
        return CompareResponse.model_validate(cached)

    try:
        result = await asyncio.to_thread(
            compare_refs,
            repository.path,
            resolved_base,
            resolved_head,
            10,
        )
    except GitStatusError:
        return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])

    cache.set(repository.id, resolved_base, resolved_head, result)
    return CompareResponse.model_validate(result)


@router.get("/repositories/{repository_id}/mirror", response_model=MirrorStatusResponse)
async def get_repository_mirror(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
) -> MirrorStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _mirror_service(request).get_mirror_status(
        repository, refresh=refresh
    )
    return MirrorStatusResponse.model_validate(snapshot)


@router.post(
    "/repositories/{repository_id}/mirror/refresh",
    response_model=MirrorStatusResponse,
)
async def refresh_repository_mirror(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MirrorStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _mirror_service(request).refresh_mirror_status(repository)
    return MirrorStatusResponse.model_validate(snapshot)


@router.patch(
    "/repositories/{repository_id}/mirror-policy",
    response_model=RepositoryRead,
)
async def update_mirror_policy(
    repository_id: int,
    payload: MirrorPolicyUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    if payload.canonical_provider is not None:
        repository.canonical_provider = payload.canonical_provider
    if payload.mirror_expected is not None:
        repository.mirror_expected = payload.mirror_expected
    if payload.mirror_policy is not None:
        repository.mirror_policy = payload.mirror_policy
    if payload.github_full_name is not None:
        repository.github_full_name = payload.github_full_name.strip() or None
    if payload.gitflic_full_name is not None:
        repository.gitflic_full_name = payload.gitflic_full_name.strip() or None
    await session.commit()
    await session.refresh(repository)
    await _mirror_service(request).invalidate(repository_id)
    return RepositoryRead.model_validate(repository)


@router.get("/mirror/candidates", response_model=MirrorCandidatesResponse)
async def mirror_candidates(request: Request) -> MirrorCandidatesResponse:
    candidates = await _mirror_service(request).discover_candidates()
    return MirrorCandidatesResponse.model_validate(candidates)


@router.post(
    "/repositories/{repository_id}/actions/{action}",
    response_model=ActionLogResponse,
)
async def run_repository_action(
    repository_id: int,
    action: str,
    payload: ActionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionLogResponse:
    repository = await _get_repository(session, repository_id)
    try:
        entry = await _action_service(request).execute_action(
            session, repository, action, confirm=payload.confirm
        )
    except UnknownActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ConfirmationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if entry.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=entry.error or entry.output or "action failed",
        )
    return ActionLogResponse.model_validate(entry)


@router.get(
    "/repositories/{repository_id}/actions",
    response_model=list[ActionLogResponse],
)
async def repository_action_history(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[ActionLogResponse]:
    await _get_repository(session, repository_id)
    rows = (
        await session.scalars(
            select(ActionLog)
            .where(ActionLog.repository_id == repository_id)
            .order_by(ActionLog.created_at.desc(), ActionLog.id.desc())
            .limit(limit)
        )
    ).all()
    return [ActionLogResponse.model_validate(row) for row in rows]


@router.post("/mirror/actions/{action}", response_model=ActionLogResponse)
async def run_mirror_action(
    action: str,
    payload: ActionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionLogResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm=true is required for mutations",
        )
    if payload.repository_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_id is required for mirror actions",
        )
    repository = await _get_repository(session, payload.repository_id)
    try:
        entry = await _action_service(request).execute_action(
            session, repository, action, confirm=payload.confirm
        )
    except (UnknownActionError, ActionNotAllowedError, ConfirmationRequiredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if entry.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=entry.error or entry.output or "action failed",
        )
    return ActionLogResponse.model_validate(entry)


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
