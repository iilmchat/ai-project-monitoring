"""Settings API (S15-001)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.settings_service import SettingsService, mask_secret

router = APIRouter(tags=["settings"])


def _service(request: Request) -> SettingsService:
    service: SettingsService = request.app.state.settings_service
    return service


def _response(values: dict[str, str | None]) -> SettingsResponse:
    return SettingsResponse(
        scan_roots=values.get("scan_roots") or "",
        github_token=mask_secret(values.get("github_token")),
        gitflic_token=mask_secret(values.get("gitflic_token")),
        webhook_secret=mask_secret(values.get("webhook_secret")),
        default_canonical_provider=values.get("default_canonical_provider") or "github",
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(request: Request) -> SettingsResponse:
    return _response(await _service(request).get_settings())


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, request: Request) -> SettingsResponse:
    try:
        values = await _service(request).update_settings(
            payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _response(values)


__all__ = ["router"]
