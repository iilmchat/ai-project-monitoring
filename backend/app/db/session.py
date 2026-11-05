"""Async engine / session plumbing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory for a file-based SQLite database."""
    if not url.startswith("sqlite"):
        return
    if "///" not in url:
        return
    raw_path = url.split("///", 1)[1]
    if not raw_path or raw_path.startswith(":memory:"):
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    ensure_sqlite_directory(database_url)
    return create_async_engine(database_url, echo=echo, future=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session bound to the app's engine."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
