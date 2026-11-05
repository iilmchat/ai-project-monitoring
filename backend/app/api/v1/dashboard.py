"""Dashboard aggregation endpoint (SPEC §3.6, S4-001)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.dashboard import DashboardRepository, DashboardResponse, DashboardSummary
from app.schemas.repository import RepositoryRead, RepositoryStatusResponse
from app.services.status_service import snapshot_from_row

router = APIRouter(tags=["dashboard"])

NEEDS_ATTENTION_STATES = frozenset({"dirty", "ahead", "behind", "diverged", "no_upstream"})
STALE_REMOTE_STATUSES = frozenset({"stale", "unavailable"})


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    session: Annotated[AsyncSession, Depends(get_session)],
    tracked_only: Annotated[bool, Query()] = False,
) -> DashboardResponse:
    statement = (
        select(Repository)
        .options(selectinload(Repository.status))
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

    for repository in repositories:
        if not repository.tracked:
            untracked += 1

        repo_status = repository.status
        if repo_status is None:
            continue

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
    )

    items: list[DashboardRepository] = []
    for repository in repositories:
        base = RepositoryRead.model_validate(repository)
        row_status = repository.status
        status_response = (
            RepositoryStatusResponse.model_validate(
                snapshot_from_row(repository, row_status)
            )
            if row_status is not None
            else None
        )
        items.append(DashboardRepository(**base.model_dump(), status=status_response))

    return DashboardResponse(summary=summary, repositories=items)
