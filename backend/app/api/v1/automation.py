"""Automation config API (v1.3.0, Sprint 59)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Repository
from app.schemas.automation import (
    AutomationConfigResponse,
    AutomationGenerateRequest,
)
from app.services.automation_service import AutomationService

router = APIRouter(tags=["automation"])


def _service(request: Request) -> AutomationService:
    service: AutomationService = request.app.state.automation_service
    return service


@router.post(
    "/repositories/{repository_id}/automation/generate",
    response_model=AutomationConfigResponse,
)
async def generate_automation(
    repository_id: int,
    payload: AutomationGenerateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AutomationConfigResponse:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="repository_not_found",
        )
    config = _service(request).generate(repository.path, payload.tool)
    return AutomationConfigResponse(
        tool=config.tool,
        path=config.path,
        content=config.content,
        content_hash=config.content_hash,
        ecosystems=config.ecosystems,
        warnings=config.warnings,
    )


__all__ = ["router"]
