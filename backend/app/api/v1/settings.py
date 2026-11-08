"""Settings API (S15-001)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.ai import LLMTestResponse
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.llm_service import LLMService
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
        llm_enabled=_as_bool(values.get("llm_enabled")),
        llm_base_url=values.get("llm_base_url") or "http://127.0.0.1:1234/v1",
        llm_model=values.get("llm_model") or "qwen2.5-coder-7b-instruct",
        llm_api_key=mask_secret(values.get("llm_api_key")),
        llm_timeout_seconds=_as_int(values.get("llm_timeout_seconds"), 30),
        llm_max_diff_chars=_as_int(values.get("llm_max_diff_chars"), 10000),
        llm_allow_remote=_as_bool(values.get("llm_allow_remote")),
        telegram_bot_token=mask_secret(values.get("telegram_bot_token")),
        telegram_chat_id=values.get("telegram_chat_id") or "",
        notifications_enabled=_as_bool(values.get("notifications_enabled")),
        fetch_timeout=_as_int(values.get("fetch_timeout"), 30),
        status_ttl_seconds=_as_int(values.get("status_ttl_seconds"), 60),
        mirror_poll_interval_seconds=_as_int(
            values.get("mirror_poll_interval_seconds"), 300
        ),
    )


def _as_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(float(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(request: Request) -> SettingsResponse:
    return _response(await _service(request).get_settings())


@router.post("/settings/llm/test", response_model=LLMTestResponse)
async def test_llm(request: Request) -> LLMTestResponse:
    service: LLMService = request.app.state.llm_service
    ok, latency_ms, error = await service.test_connection()
    return LLMTestResponse(
        status="ok" if ok else "error",
        latency_ms=latency_ms,
        error=error,
    )


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
