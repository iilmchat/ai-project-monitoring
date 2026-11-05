"""Shared fixtures for backend tests."""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from app.config import Settings
from app.db.base import Base
from app.main import create_app
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        scan_roots=str(tmp_path),
        scan_depth=3,
        scan_ignore="node_modules,.venv,vendor,dist,build,target",
        scan_concurrency=4,
        debug=False,
    )


@pytest_asyncio.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield application
    finally:
        await application.state.engine.dispose()


@pytest_asyncio.fixture
async def session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = app.state.session_factory
    return factory


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
def make_repo() -> Callable[[Path], Path]:
    """Return a factory creating a real Git repository at ``path``."""

    def _make(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(path)],
            check=True,
            capture_output=True,
        )
        return path

    return _make
