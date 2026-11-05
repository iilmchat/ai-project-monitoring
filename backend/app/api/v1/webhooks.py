"""GitHub / GitFlic webhook ingestion (SPEC §3.8.4, R9, S9-008)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import Settings
from app.db.base import utcnow
from app.models.entities import Repository, RepositoryMirrorStatus, WebhookEvent

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])

SIGNATURE_HEADERS = ("x-hub-signature-256", "x-gitflic-signature", "x-hub-signature")
EVENT_HEADERS = ("x-github-event", "x-gitflic-event")


def _valid_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    candidate = signature.strip()
    if candidate.startswith("sha256="):
        candidate = candidate[len("sha256=") :]
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, candidate.lower())


def _extract_event_type(request: Request, payload: dict[str, Any]) -> str:
    for header in EVENT_HEADERS:
        value = request.headers.get(header)
        if value:
            return value
    for key in ("event_type", "event", "type"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _extract_full_name(payload: dict[str, Any]) -> str | None:
    repository = payload.get("repository")
    if isinstance(repository, dict):
        full_name = repository.get("full_name")
        if full_name:
            return str(full_name)
        name = repository.get("name")
        owner = repository.get("owner")
        if name and isinstance(owner, dict):
            login = owner.get("login") or owner.get("alias") or owner.get("username")
            if login:
                return f"{login}/{name}"

    project = payload.get("project")
    if isinstance(project, dict):
        full_name = project.get("full_name")
        if full_name:
            return str(full_name)
        alias = project.get("alias") or project.get("name")
        owner = project.get("owner")
        if alias and isinstance(owner, dict):
            login = owner.get("alias") or owner.get("login") or owner.get("username")
            if login:
                return f"{login}/{alias}"

    for key in ("repository_full_name", "full_name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


async def _handle_webhook(provider: str, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    body = await request.body()

    signature = next(
        (request.headers[header] for header in SIGNATURE_HEADERS if header in request.headers),
        None,
    )
    if settings.webhook_secret and not _valid_signature(
        settings.webhook_secret, body, signature
    ):
        logger.warning("webhook_rejected", provider=provider)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid webhook signature",
        )

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid JSON payload",
        ) from exc

    event_type = _extract_event_type(request, payload)
    full_name = _extract_full_name(payload)

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repository: Repository | None = None
        if full_name:
            column = (
                Repository.github_full_name
                if provider == "github"
                else Repository.gitflic_full_name
            )
            repository = await session.scalar(select(Repository).where(column == full_name))

        now = utcnow()
        session.add(
            WebhookEvent(
                provider=provider,
                event_type=event_type,
                repository_id=repository.id if repository is not None else None,
                payload=payload,
                received_at=now,
                processed_at=now,
                status="processed",
            )
        )

        if repository is not None:
            mirror_row = await session.scalar(
                select(RepositoryMirrorStatus).where(
                    RepositoryMirrorStatus.repository_id == repository.id
                )
            )
            if mirror_row is not None:
                await session.delete(mirror_row)
        await session.commit()

    logger.info(
        "webhook_received",
        provider=provider,
        event_type=event_type,
        full_name=full_name,
        repository_id=repository.id if repository is not None else None,
    )
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "accepted"})


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(request: Request) -> JSONResponse:
    return await _handle_webhook("github", request)


@router.post("/webhooks/gitflic", status_code=status.HTTP_202_ACCEPTED)
async def gitflic_webhook(request: Request) -> JSONResponse:
    return await _handle_webhook("gitflic", request)


__all__ = ["router"]
