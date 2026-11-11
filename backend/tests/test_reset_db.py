"""Database reset API tests (S60-Fix-003)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.models.entities import Repository
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_reset_db_wipes_data_and_recreates_admin(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    repo = make_repo(tmp_path / "repo")
    async with session_factory() as session:
        session.add(Repository(path=str(repo.resolve()), tracked=True))
        await session.commit()

    response = await client.post(
        "/api/v1/auth/reset-db",
        json={"confirm": True},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    async with session_factory() as session:
        repositories = await session.scalar(
            select(func.count()).select_from(Repository)
        )
    assert repositories == 0

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "admin"


async def test_reset_db_requires_explicit_confirmation(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/reset-db",
        json={"confirm": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "confirmation_required"
