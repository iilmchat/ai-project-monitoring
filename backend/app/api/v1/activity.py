"""Contribution activity heatmap (S21-004)."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.git.command_backend import commit_dates
from app.models.entities import Repository

router = APIRouter(tags=["activity"])

CONCURRENCY = 5


@router.get("/dashboard/heatmap", response_model=dict[str, int])
async def dashboard_heatmap(
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=3650)] = 365,
) -> dict[str, int]:
    repositories = (
        await session.scalars(
            select(Repository).where(Repository.tracked.is_(True)).order_by(Repository.path)
        )
    ).all()
    since = (date.today() - timedelta(days=days)).isoformat()
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def worker(path: str) -> list[str]:
        async with semaphore:
            return await asyncio.to_thread(commit_dates, path, since)

    batches = await asyncio.gather(*(worker(repo.path) for repo in repositories))
    counter: Counter[str] = Counter()
    for dates in batches:
        counter.update(dates)
    return dict(sorted(counter.items()))


__all__ = ["router"]
