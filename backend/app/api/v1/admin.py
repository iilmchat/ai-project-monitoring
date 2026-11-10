"""Action audit endpoint (S10-005)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_session
from app.models.entities import ActionLog
from app.schemas.action import ActionLogResponse

router = APIRouter(tags=["admin"])


@router.get(
    "/admin/actions",
    response_model=list[ActionLogResponse],
    dependencies=[Depends(require_admin)],
)
async def list_actions(
    session: Annotated[AsyncSession, Depends(get_session)],
    repository_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[ActionLogResponse]:
    statement = select(ActionLog).order_by(ActionLog.created_at.desc(), ActionLog.id.desc())
    if repository_id is not None:
        statement = statement.where(ActionLog.repository_id == repository_id)
    rows = (await session.scalars(statement.limit(limit))).all()
    return [ActionLogResponse.model_validate(row) for row in rows]


__all__ = ["router"]
