"""Repository listing endpoint (SPEC §3.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.repository import RepositoryListResponse, RepositoryRead

router = APIRouter(tags=["repositories"])


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
