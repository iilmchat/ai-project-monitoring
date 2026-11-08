"""AI provider profile API (S39-001)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.models.entities import AIProviderProfile
from app.schemas.ai_provider import (
    AIProviderCreate,
    AIProviderRead,
    AIProviderUpdate,
)
from app.services.ai_provider_service import (
    AIProviderConflictError,
    AIProviderNotFoundError,
    AIProviderService,
)
from app.services.settings_service import mask_secret

router = APIRouter(tags=["ai-providers"])


def _provider_service(request: Request) -> AIProviderService:
    service: AIProviderService = request.app.state.ai_provider_service
    return service


def _read(profile: AIProviderProfile) -> AIProviderRead:
    return AIProviderRead(
        id=profile.id,
        name=profile.name,
        base_url=profile.base_url,
        api_key=mask_secret(profile.api_key) if profile.api_key else "",
        model_name=profile.model_name,
        is_active=profile.is_active,
        created_at=profile.created_at,
    )


@router.get(
    "/settings/ai-providers",
    response_model=list[AIProviderRead],
)
async def list_ai_providers(request: Request) -> list[AIProviderRead]:
    service = _provider_service(request)
    return [_read(profile) for profile in await service.list_profiles()]


@router.post(
    "/settings/ai-providers",
    response_model=AIProviderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_provider(
    payload: AIProviderCreate,
    request: Request,
) -> AIProviderRead:
    service = _provider_service(request)
    try:
        profile = await service.create(
            name=payload.name,
            base_url=payload.base_url,
            model_name=payload.model_name,
            api_key=payload.api_key,
        )
    except AIProviderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _read(profile)


@router.patch(
    "/settings/ai-providers/{profile_id}",
    response_model=AIProviderRead,
)
async def update_ai_provider(
    profile_id: int,
    payload: AIProviderUpdate,
    request: Request,
) -> AIProviderRead:
    service = _provider_service(request)
    try:
        profile = await service.update(
            profile_id,
            name=payload.name,
            base_url=payload.base_url,
            model_name=payload.model_name,
            api_key=payload.api_key,
        )
    except AIProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _read(profile)


@router.delete(
    "/settings/ai-providers/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_ai_provider(profile_id: int, request: Request) -> None:
    service = _provider_service(request)
    try:
        await service.delete(profile_id)
    except AIProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/settings/ai-providers/{profile_id}/activate",
    response_model=AIProviderRead,
)
async def activate_ai_provider(
    profile_id: int,
    request: Request,
) -> AIProviderRead:
    service = _provider_service(request)
    try:
        profile = await service.activate(profile_id)
    except AIProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _read(profile)


__all__ = ["router"]
