"""Webhook HMAC validation and cache invalidation tests (S9-008)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from app.models.entities import Repository, RepositoryMirrorStatus, WebhookEvent
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

SECRET = "test-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str((tmp_path / "repo").resolve()),
            tracked=True,
            github_full_name="acme/app",
            gitflic_full_name="acme/app",
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        session.add(
            RepositoryMirrorStatus(
                repository_id=repository.id,
                mirror_status="behind_gitflic",
                details={},
            )
        )
        await session.commit()
        return repository.id


async def _count_events(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count(WebhookEvent.id))) or 0)


async def test_github_webhook_validates_and_invalidates(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.settings.webhook_secret = SECRET

    body = json.dumps(
        {"repository": {"full_name": "acme/app"}, "ref": "refs/heads/main"}
    ).encode()
    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
            "X-GitHub-Event": "push",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}

    async with session_factory() as session:
        event = await session.scalar(select(WebhookEvent))
        mirror_exists = await session.scalar(
            select(RepositoryMirrorStatus).where(
                RepositoryMirrorStatus.repository_id == repository_id
            )
        )
    assert event is not None
    assert event.provider == "github"
    assert event.event_type == "push"
    assert event.repository_id == repository_id
    assert event.status == "processed"
    assert mirror_exists is None


async def test_webhook_rejects_invalid_signature(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_repository(session_factory, tmp_path)
    app.state.settings.webhook_secret = SECRET

    body = b'{"repository": {"full_name": "acme/app"}}'
    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Event": "push",
        },
    )

    assert response.status_code == 401
    assert await _count_events(session_factory) == 0


async def test_gitflic_webhook(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.settings.webhook_secret = SECRET

    body = json.dumps(
        {"project": {"full_name": "acme/app"}, "event": "push"}
    ).encode()
    response = await client.post(
        "/api/v1/webhooks/gitflic",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Gitflic-Signature": _sign(body),
        },
    )

    assert response.status_code == 202
    async with session_factory() as session:
        event = await session.scalar(select(WebhookEvent))
    assert event is not None
    assert event.provider == "gitflic"
    assert event.repository_id == repository_id


async def test_webhook_accepted_without_secret(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _create_repository(session_factory, tmp_path)
    app.state.settings.webhook_secret = ""

    body = b'{"repository": {"full_name": "acme/app"}}'
    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"Content-Type": "application/json", "X-GitHub-Event": "push"},
    )

    assert response.status_code == 202
