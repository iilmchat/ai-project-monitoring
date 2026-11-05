"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import Settings
from app.db.session import build_engine, build_session_factory
from app.logging import configure_logging
from app.middleware import RequestLoggingMiddleware

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

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "app_started",
            version=resolved.app_version,
            database_url=resolved.database_url,
            scan_roots=resolved.scan_root_paths,
        )
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("app_stopped")

    application = FastAPI(
        title="IIRuchating API",
        version=resolved.app_version,
        description="Monitoring of local Git repositories (read-only).",
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.add_middleware(RequestLoggingMiddleware)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
