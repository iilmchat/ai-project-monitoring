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
from app.middleware import AuthMiddleware, RequestLoggingMiddleware
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient
from app.providers.npm_client import NpmClient
from app.providers.osv_client import OsvClient
from app.providers.pypi_client import PypiClient
from app.services.action_service import ActionService
from app.services.agent_task_service import AgentTaskService
from app.services.ai_provider_service import AIProviderService
from app.services.auth_service import AuthService
from app.services.bulk_service import BulkService
from app.services.ci_service import CIService
from app.services.code_search_service import CodeSearchService
from app.services.compare_cache import CompareCache
from app.services.dashboard_advice_service import DashboardAdviceService
from app.services.dependency_service import DependencyService
from app.services.dependency_update_service import DependencyUpdateService
from app.services.docker_service import DockerService
from app.services.gigachat_provider import GigaChatProvider
from app.services.global_analytics_service import GlobalAnalyticsService
from app.services.identity_service import IdentityService
from app.services.insights_service import InsightsService
from app.services.llm_service import LLMService
from app.services.mirror_scheduler import MirrorScheduler
from app.services.mirror_service import MirrorService
from app.services.notification_service import NotificationService
from app.services.remote_service import RemoteService
from app.services.security_service import SecurityService
from app.services.settings_service import SettingsService
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
    notification_service = NotificationService(
        enabled=resolved.notifications_enabled,
        notify_on=set(resolved.notify_on_names),
        bot_token=resolved.telegram_bot_token,
        chat_id=resolved.telegram_chat_id,
    )
    status_service = StatusService(
        status_cache,
        ttl_seconds=resolved.status_ttl_seconds,
        remote_service=remote_service,
        notifications=notification_service,
    )
    github_client = GitHubClient(
        resolved.github_token,
        timeout=resolved.provider_timeout_seconds,
        cache_ttl_seconds=resolved.provider_cache_ttl_seconds,
    )
    gitflic_client = GitFlicClient(
        resolved.gitflic_token,
        timeout=resolved.provider_timeout_seconds,
        cache_ttl_seconds=resolved.provider_cache_ttl_seconds,
    )
    mirror_service = MirrorService(
        session_factory,
        github_client,
        gitflic_client,
        ttl_seconds=resolved.mirror_status_ttl_seconds,
    )
    ci_service = CIService(
        github_client,
        gitflic_client,
        resolved,
        ttl_seconds=resolved.provider_cache_ttl_seconds,
        concurrency=resolved.scan_concurrency,
    )
    docker_service = DockerService(
        enabled=resolved.docker_enabled,
        host=resolved.docker_host or None,
        path_map=resolved.docker_path_map,
        timeout_seconds=resolved.docker_timeout_seconds,
        cache_ttl_seconds=resolved.docker_status_ttl_seconds,
    )
    pypi_client = PypiClient(timeout_seconds=resolved.dependency_http_timeout)
    npm_client = NpmClient(timeout_seconds=resolved.dependency_http_timeout)
    dependency_service = DependencyService(
        session_factory,
        pypi_client,
        npm_client,
        cache_ttl_seconds=resolved.dependency_cache_ttl_seconds,
        concurrency=resolved.dependency_check_concurrency,
        manifest_max_depth=resolved.dependency_manifest_max_depth,
    )
    osv_client = OsvClient(
        timeout_seconds=resolved.security_http_timeout,
        base_url=resolved.osv_api_url,
    )
    security_service = SecurityService(
        session_factory,
        osv_client,
        cache_ttl_seconds=resolved.security_cache_ttl_seconds,
        concurrency=resolved.security_check_concurrency,
        manifest_max_depth=resolved.dependency_manifest_max_depth,
        secret_scan_enabled=resolved.secret_scan_enabled,
        secret_scan_max_files=resolved.secret_scan_max_files,
        secret_scan_max_file_bytes=resolved.secret_scan_max_file_bytes,
        secret_scan_ttl_seconds=resolved.secret_scan_ttl_seconds,
    )
    insights_service = InsightsService(
        cache_ttl_seconds=resolved.insights_cache_ttl_seconds,
        timeout_seconds=resolved.insights_git_timeout_seconds,
        hotspots_limit=resolved.insights_hotspots_limit,
        hotspots_days=resolved.insights_hotspots_days,
    )
    ai_provider_service = AIProviderService(session_factory)
    gigachat_provider = GigaChatProvider(resolved, session_factory=session_factory)
    llm_service = LLMService(
        resolved,
        session_factory=session_factory,
        gigachat=gigachat_provider,
    )
    global_analytics_service = GlobalAnalyticsService(
        session_factory,
        dependency_service,
        cache_ttl_seconds=resolved.global_analytics_cache_ttl_seconds,
        limit=resolved.global_analytics_limit,
        concurrency=resolved.global_analytics_concurrency,
        llm_service=llm_service,
        ai_cache_ttl_seconds=resolved.ai_cache_ttl_seconds,
        prompt_version=resolved.ai_prompt_version,
    )
    identity_service = IdentityService(session_factory)
    code_search_service = CodeSearchService(
        session_factory,
        resolved,
        llm_service,
        database_url=resolved.database_url,
    )
    dashboard_advice_service = DashboardAdviceService(
        session_factory,
        dependency_service,
        security_service,
        llm_service,
        prompt_version=resolved.ai_prompt_version,
    )
    agent_task_service = AgentTaskService(llm_service)
    dependency_update_service = DependencyUpdateService(
        session_factory,
        timeout_seconds=resolved.dependency_update_timeout_seconds,
        max_output_chars=resolved.dependency_update_max_output_chars,
    )
    mirror_scheduler = MirrorScheduler(
        mirror_service,
        session_factory,
        interval_seconds=resolved.mirror_poll_interval_seconds,
        notifications=notification_service,
    )
    action_service = ActionService(timeout_seconds=resolved.action_timeout_seconds)
    bulk_service = BulkService(
        session_factory,
        concurrency=resolved.scan_concurrency,
        fetch_timeout=resolved.fetch_timeout,
        action_timeout=resolved.action_timeout_seconds,
    )
    settings_service = SettingsService(
        session_factory,
        resolved,
        github_client=github_client,
        gitflic_client=gitflic_client,
        remote_service=remote_service,
        status_cache=status_cache,
        status_service=status_service,
        mirror_scheduler=mirror_scheduler,
        notification_service=notification_service,
    )
    auth_service = AuthService(session_factory, resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "app_started",
            version=resolved.app_version,
            database_url=resolved.database_url,
            scan_roots=resolved.scan_root_paths,
        )
        await settings_service.load_into_config()
        await auth_service.bootstrap_admin()
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
    application.state.ci_service = ci_service
    application.state.docker_service = docker_service
    application.state.pypi_client = pypi_client
    application.state.npm_client = npm_client
    application.state.dependency_service = dependency_service
    application.state.osv_client = osv_client
    application.state.security_service = security_service
    application.state.insights_service = insights_service
    application.state.llm_service = llm_service
    application.state.gigachat_provider = gigachat_provider
    application.state.global_analytics_service = global_analytics_service
    application.state.identity_service = identity_service
    application.state.code_search_service = code_search_service
    application.state.dashboard_advice_service = dashboard_advice_service
    application.state.agent_task_service = agent_task_service
    application.state.ai_provider_service = ai_provider_service
    application.state.dependency_update_service = dependency_update_service
    application.state.mirror_scheduler = mirror_scheduler
    application.state.action_service = action_service
    application.state.bulk_service = bulk_service
    application.state.settings_service = settings_service
    application.state.auth_service = auth_service
    application.state.notification_service = notification_service
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
