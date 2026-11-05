"""Prometheus metrics endpoint (SPEC §3.10, S8-002)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import set_mirror_status_counts, set_repository_state_counts
from app.db.session import get_session
from app.models.entities import RepositoryMirrorStatus, RepositoryStatus

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    rows = await session.execute(
        select(RepositoryStatus.state, func.count(RepositoryStatus.id)).group_by(
            RepositoryStatus.state
        )
    )
    counts = {state: count for state, count in rows.all()}
    set_repository_state_counts(counts)

    mirror_rows = await session.execute(
        select(
            RepositoryMirrorStatus.mirror_status,
            func.count(RepositoryMirrorStatus.id),
        ).group_by(RepositoryMirrorStatus.mirror_status)
    )
    set_mirror_status_counts({status: count for status, count in mirror_rows.all()})

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
