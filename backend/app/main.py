"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import Settings
from app.core.system import read_git_version
from app.db.session import build_engine, build_session_factory
from app.logging import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient
from app.services.action_service import ActionService
from app.services.compare_cache import CompareCache
from app.services.mirror_scheduler import MirrorScheduler
from app.services.mirror_service import MirrorService
from app.services.remote_service import RemoteService
from app.services.status_service import StatusCache, StatusService

logger = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    The engine and session factory are created eagerly so tests can create the
    schema and query the same engine without running the lifespan context.
    """
    resolved = settings or Settings()
    configure_logging(debug=resolved.debug)

    engine = build_engine(resolved.database_url)
    session_factory = build_session_factory(engine)
    status_cache = StatusCache(ttl_seconds=resolved.status_ttl_seconds)
    compare_cache = CompareCache(ttl_seconds=resolved.compare_ttl_seconds)
    remote_service = RemoteService(timeout_seconds=resolved.fetch_timeout)
    status_service = StatusService(
        status_cache,
        ttl_seconds=resolved.status_ttl_seconds,
        remote_service=remote_service,
    )
    github_client = GitHubClient(
        resolved.github_token, timeout=resolved.provider_timeout_seconds
    )
    gitflic_client = GitFlicClient(
        resolved.gitflic_token, timeout=resolved.provider_timeout_seconds
    )
    mirror_service = MirrorService(
        session_factory,
        github_client,
        gitflic_client,
        ttl_seconds=resolved.mirror_status_ttl_seconds,
    )
    mirror_scheduler = MirrorScheduler(
        mirror_service,
        session_factory,
        interval_seconds=resolved.mirror_poll_interval_seconds,
    )
    action_service = ActionService(timeout_seconds=resolved.action_timeout_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "app_started",
            version=resolved.app_version,
            database_url=resolved.database_url,
            scan_roots=resolved.scan_root_paths,
        )
        mirror_scheduler.start()
        try:
            yield
        finally:
            await mirror_scheduler.stop()
            await engine.dispose()
            logger.info("app_stopped")

    application: FastAPI = FastAPI(
        title="IIRuchating API",
        version=resolved.app_version,
        description="Monitoring of local Git repositories (read-only).",
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.state.git_version = read_git_version()
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.status_cache = status_cache
    application.state.compare_cache = compare_cache
    application.state.remote_service = remote_service
    application.state.status_service = status_service
    application.state.github_client = github_client
    application.state.gitflic_client = gitflic_client
    application.state.mirror_service = mirror_service
    application.state.mirror_scheduler = mirror_scheduler
    application.state.action_service = action_service
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
