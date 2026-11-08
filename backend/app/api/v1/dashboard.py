"""Dashboard aggregation endpoint (SPEC §3.6, S4-001)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.ai import DashboardAdvice, DashboardAdviceRequest
from app.schemas.ci import CISummary
from app.schemas.dashboard import DashboardRepository, DashboardResponse, DashboardSummary
from app.schemas.global_analytics import (
    GlobalDependencyReport,
    UnificationAdvice,
    UnificationAdviceRequest,
)
from app.schemas.identity import DuplicatesResponse
from app.schemas.mirror import MirrorStatusResponse
from app.schemas.repository import RepositoryRead, RepositoryStatusResponse
from app.services.dashboard_advice_service import (
    DashboardAdviceService,
    DashboardAdviceUnavailableError,
)
from app.services.global_analytics_service import (
    GlobalAnalyticsService,
    LLMUnavailableError,
    PackageNotFoundError,
    UnificationNotNeededError,
)
from app.services.identity_service import IdentityService
from app.services.mirror_service import ATTENTION_STATUSES, snapshot_from_row
from app.services.status_service import snapshot_from_row as status_snapshot_from_row

router = APIRouter(tags=["dashboard"])

NEEDS_ATTENTION_STATES = frozenset({"dirty", "ahead", "behind", "diverged", "no_upstream"})
STALE_REMOTE_STATUSES = frozenset({"stale", "unavailable"})


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    tracked_only: Annotated[bool, Query()] = False,
) -> DashboardResponse:
    statement = (
        select(Repository)
        .options(selectinload(Repository.status), selectinload(Repository.mirror))
        .order_by(Repository.path)
    )
    if tracked_only:
        statement = statement.where(Repository.tracked.is_(True))

    repositories = (await session.scalars(statement)).all()

    clean = 0
    needs_attention = 0
    untracked = 0
    stale = 0
    errors = 0
    mirror_issues = 0
    by_state: dict[str, int] = {}
    by_mirror_status: dict[str, int] = {}

    for repository in repositories:
        if not repository.tracked:
            untracked += 1

        if repository.mirror is not None:
            mirror_status = repository.mirror.mirror_status
            by_mirror_status[mirror_status] = by_mirror_status.get(mirror_status, 0) + 1
            if mirror_status in ATTENTION_STATUSES:
                mirror_issues += 1

        repo_status = repository.status
        if repo_status is None:
            continue
        by_state[repo_status.state] = by_state.get(repo_status.state, 0) + 1

        if repo_status.state == "current":
            clean += 1
        elif repo_status.state in NEEDS_ATTENTION_STATES:
            needs_attention += 1
        elif repo_status.state == "error":
            errors += 1

        if repo_status.remote_status in STALE_REMOTE_STATUSES:
            stale += 1

    summary = DashboardSummary(
        total=len(repositories),
        clean=clean,
        needs_attention=needs_attention,
        untracked=untracked,
        stale=stale,
        errors=errors,
        mirror_issues=mirror_issues,
        by_state=by_state,
        by_mirror_status=by_mirror_status,
    )

    items: list[DashboardRepository] = []
    ci_rows = [
        (
            repository.id,
            repository.status.branch if repository.status and repository.status.branch else "main",
            repository.github_full_name,
            repository.gitflic_full_name,
        )
        for repository in repositories
    ]
    ci_map = await request.app.state.ci_service.get_many(ci_rows)
    for repository in repositories:
        base = RepositoryRead.model_validate(repository)
        row_status = repository.status
        status_response = (
            RepositoryStatusResponse.model_validate(
                status_snapshot_from_row(repository, row_status)
            )
            if row_status is not None
            else None
        )
        mirror_response = (
            MirrorStatusResponse.model_validate(snapshot_from_row(repository, repository.mirror))
            if repository.mirror is not None
            else None
        )
        ci_summary = ci_map.get(repository.id)
        items.append(
            DashboardRepository(
                **base.model_dump(),
                status=status_response,
                mirror=mirror_response,
                ci=(
                    CISummary(
                        github=ci_summary.github,
                        gitflic=ci_summary.gitflic,
                        aggregate=ci_summary.aggregate,
                    )
                    if ci_summary
                    else None
                ),
            )
        )

    return DashboardResponse(summary=summary, repositories=items)


@router.get(
    "/dashboard/global-dependencies",
    response_model=GlobalDependencyReport,
)
async def get_global_dependencies(
    request: Request,
    refresh: Annotated[bool, Query()] = False,
) -> GlobalDependencyReport:
    service: GlobalAnalyticsService = request.app.state.global_analytics_service
    return await service.get_global_dependencies(refresh=refresh)


@router.post("/ai/dashboard-advice", response_model=DashboardAdvice)
async def get_dashboard_advice(
    request: Request,
    payload: DashboardAdviceRequest | None = None,
) -> DashboardAdvice:
    service: DashboardAdviceService = request.app.state.dashboard_advice_service
    try:
        return await service.get_advice(payload.language if payload else "ru")
    except DashboardAdviceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/dashboard/duplicates", response_model=DuplicatesResponse)
async def get_remote_duplicates(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DuplicatesResponse:
    service: IdentityService = request.app.state.identity_service
    groups = await service.find_remote_duplicates()
    checked = await session.scalar(select(func.count(Repository.id))) or 0
    return DuplicatesResponse(
        checked=checked,
        groups=[
            {
                "remote_url": group.remote_url,
                "repositories": [
                    {"id": item.id, "path": item.path, "name": item.name}
                    for item in group.repositories
                ],
            }
            for group in groups
        ],
    )


@router.post(
    "/dashboard/global-dependencies/ai-advice",
    response_model=UnificationAdvice,
)
async def get_unification_advice(
    payload: UnificationAdviceRequest,
    request: Request,
) -> UnificationAdvice:
    service: GlobalAnalyticsService = request.app.state.global_analytics_service
    try:
        return await service.get_ai_unification_advice(
            payload.ecosystem,
            payload.package,
        )
    except PackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnificationNotNeededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
