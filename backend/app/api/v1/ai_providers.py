"""AI provider profile API (S39-001, GigaChat OAuth S43-002)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import actor_id, require_admin
from app.models.entities import AIProviderProfile
from app.schemas.ai_provider import (
    AIProviderCreate,
    AIProviderRead,
    AIProviderUpdate,
    GigaChatAuthRequest,
    GigaChatAuthResponse,
)
from app.services.ai_provider_service import (
    AIProviderConflictError,
    AIProviderNotFoundError,
    AIProviderService,
)
from app.services.gigachat_provider import GigaChatError, GigaChatProvider
from app.services.settings_service import mask_secret

router = APIRouter(tags=["ai-providers"])


def _provider_service(request: Request) -> AIProviderService:
    service: AIProviderService = request.app.state.ai_provider_service
    return service


def _gigachat(request: Request) -> GigaChatProvider:
    provider: GigaChatProvider = request.app.state.gigachat_provider
    return provider


def _read(profile: AIProviderProfile) -> AIProviderRead:
    return AIProviderRead(
        id=profile.id,
        name=profile.name,
        base_url=profile.base_url,
        api_key=mask_secret(profile.api_key) if profile.api_key else "",
        model_name=profile.model_name,
        embedding_model=profile.embedding_model,
        is_active=profile.is_active,
        created_at=profile.created_at,
        provider_type=profile.provider_type or "openai_compatible",
        auth_type=profile.auth_type or "api_key",
        client_id=profile.client_id or "",
        has_client_secret=bool(profile.client_secret),
        oauth_scope=profile.oauth_scope,
        oauth_expires_at=profile.oauth_expires_at,
    )


def _auth_error(exc: GigaChatError) -> HTTPException:
    if exc.code in {"invalid_client", "unsupported_scope"}:
        code = status.HTTP_400_BAD_REQUEST
    elif exc.code in {"timeout", "provider_unavailable"}:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exc.code == "provider_unauthorized":
        code = status.HTTP_401_UNAUTHORIZED
    else:
        code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=code, detail=exc.code)


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
    dependencies=[Depends(require_admin)],
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
            embedding_model=payload.embedding_model,
            api_key=payload.api_key,
            provider_type=payload.provider_type,
            auth_type=payload.auth_type,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            oauth_scope=payload.oauth_scope,
        )
    except AIProviderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await request.app.state.audit_service.log(
        actor_id(request),
        "settings_updated",
        "ai_provider",
        profile.id,
        {"operation": "create", "name": profile.name},
    )
    return _read(profile)


@router.post(
    "/settings/ai-providers/gigachat/auth",
    response_model=GigaChatAuthResponse,
    dependencies=[Depends(require_admin)],
)
async def authorize_gigachat(
    payload: GigaChatAuthRequest,
    request: Request,
) -> GigaChatAuthResponse:
    provider = _gigachat(request)
    try:
        token = await provider.authorize(
            payload.client_id,
            payload.client_secret,
            payload.scope,
        )
    except GigaChatError as exc:
        raise _auth_error(exc) from exc

    service = _provider_service(request)
    base_url = payload.base_url or request.app.state.settings.gigachat_api_url
    try:
        profile = await service.upsert_gigachat(
            name=payload.profile_name,
            base_url=base_url,
            model_name=payload.model_name,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            scope=payload.scope,
            expires_at=token.expires_at,
            access_token=token.access_token,
            activate=payload.activate,
        )
    except AIProviderConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    provider.remember(profile.id, token)
    return GigaChatAuthResponse(
        profile_id=profile.id,
        expires_at=token.expires_at,
        model_name=profile.model_name,
    )


@router.post(
    "/settings/ai-providers/{profile_id}/gigachat/refresh",
    response_model=GigaChatAuthResponse,
    dependencies=[Depends(require_admin)],
)
async def refresh_gigachat(
    profile_id: int,
    request: Request,
) -> GigaChatAuthResponse:
    service = _provider_service(request)
    try:
        profile = await service.get(profile_id)
    except AIProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if (profile.provider_type or "") != "gigachat":
        raise HTTPException(
            status_code=400,
            detail="profile is not a gigachat provider",
        )
    provider = _gigachat(request)
    try:
        token = await provider.authorize(
            profile.client_id or "",
            profile.client_secret or "",
            profile.oauth_scope or "GIGACHAT_API_PERS",
        )
    except GigaChatError as exc:
        raise _auth_error(exc) from exc
    updated = await service.upsert_gigachat(
        name=profile.name,
        base_url=profile.base_url,
        model_name=profile.model_name,
        client_id=profile.client_id or "",
        client_secret=profile.client_secret or "",
        scope=profile.oauth_scope or "GIGACHAT_API_PERS",
        expires_at=token.expires_at,
        access_token=token.access_token,
        activate=profile.is_active,
    )
    provider.remember(updated.id, token)
    return GigaChatAuthResponse(
        profile_id=updated.id,
        expires_at=token.expires_at,
        model_name=updated.model_name,
    )


@router.patch(
    "/settings/ai-providers/{profile_id}",
    response_model=AIProviderRead,
    dependencies=[Depends(require_admin)],
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
            embedding_model=payload.embedding_model,
            api_key=payload.api_key,
            provider_type=payload.provider_type,
            auth_type=payload.auth_type,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            oauth_scope=payload.oauth_scope,
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
    dependencies=[Depends(require_admin)],
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
    dependencies=[Depends(require_admin)],
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
