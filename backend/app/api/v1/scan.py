"""Discovery scan endpoints (SPEC §3.2, S1-003)."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.base import utcnow
from app.models.entities import ScanRun
from app.schemas.scan import ScanRequest, ScanResponse, ScanStarted
from app.services.discovery_service import DiscoveryService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["scan"])


def _factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


async def _mark_failed(
    factory: async_sessionmaker[AsyncSession], scan_run_id: int, message: str
) -> None:
    async with factory() as session:
        run = await session.get(ScanRun, scan_run_id)
        if run is None:
            return
        run.status = "failed"
        run.finished_at = utcnow()
        run.errors = [*run.errors, message]
        await session.commit()


async def _execute_scan(
    factory: async_sessionmaker[AsyncSession],
    scan_run_id: int,
    roots: list[str],
    depth: int,
    ignore: list[str],
) -> None:
    service = DiscoveryService(factory)
    try:
        await service.scan_directory(roots, depth, ignore, scan_run_id=scan_run_id)
    except Exception as exc:  # background task must not crash the worker
        logger.exception("scan_failed", scan_run_id=scan_run_id)
        await _mark_failed(factory, scan_run_id, str(exc))


@router.post("/scan", response_model=ScanStarted, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: ScanRequest | None = None,
) -> ScanStarted:
    settings: Settings = request.app.state.settings
    factory = _factory(request)

    roots = (payload.roots if payload and payload.roots else settings.scan_root_paths)
    depth = payload.depth if payload and payload.depth is not None else settings.scan_depth
    ignore = settings.scan_ignore_names

    async with factory() as session:
        run = ScanRun(
            started_at=utcnow(),
            status="pending",
            roots=roots,
            depth=depth,
            errors=[],
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

    background_tasks.add_task(_execute_scan, factory, run.id, roots, depth, ignore)
    logger.info("scan_requested", scan_run_id=run.id, roots=roots, depth=depth)
    return ScanStarted(scan_id=run.id, started_at=run.started_at)


@router.get("/scan/latest", response_model=ScanResponse)
async def latest_scan(request: Request) -> ScanResponse:
    factory = _factory(request)
    async with factory() as session:
        run = await session.scalar(
            select(ScanRun).order_by(ScanRun.started_at.desc(), ScanRun.id.desc()).limit(1)
        )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no scans yet")
    return ScanResponse.model_validate(run)


@router.get("/scan/{scan_id}", response_model=ScanResponse)
async def scan_status(scan_id: int, request: Request) -> ScanResponse:
    factory = _factory(request)
    async with factory() as session:
        run = await session.get(ScanRun, scan_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scan not found")
    return ScanResponse.model_validate(run)
