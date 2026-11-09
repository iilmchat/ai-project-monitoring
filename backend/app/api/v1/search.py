"""RAG code search API (SPEC §3.26, S44)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.db.base import utcnow
from app.schemas.code_search import (
    ChatRequest,
    ChatResponse,
    CodeIndexJob,
    CodeIndexRequest,
    CodeIndexStatus,
    CodeSearchRequest,
    CodeSearchResponse,
)
from app.services.code_search_service import (
    CodeSearchService,
    RagBusyError,
    RagUnavailableError,
)

router = APIRouter(tags=["search"])


def _service(request: Request) -> CodeSearchService:
    service: CodeSearchService = request.app.state.code_search_service
    return service


def _unavailable(exc: RagUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=exc.code,
    )


async def _run_index(
    service: CodeSearchService,
    repository_ids: list[int] | None,
    force: bool,
) -> None:
    try:
        await service.index(repository_ids, force=force)
    except RagBusyError:
        return
    except RagUnavailableError:
        return


@router.post("/search/code", response_model=CodeSearchResponse)
async def search_code(
    payload: CodeSearchRequest,
    request: Request,
) -> CodeSearchResponse:
    try:
        return await _service(request).search(
            payload.query,
            repository_ids=payload.repository_ids,
            limit=payload.limit,
            min_score=payload.min_score,
            language=payload.language,
        )
    except RagUnavailableError as exc:
        raise _unavailable(exc) from exc


@router.post("/search/chat", response_model=ChatResponse)
async def chat_with_code(
    payload: ChatRequest,
    request: Request,
) -> ChatResponse:
    try:
        result = await _service(request).chat_with_code(
            payload.query,
            [message.model_dump() for message in payload.history],
            repository_ids=payload.repository_ids,
            limit=payload.limit,
            min_score=payload.min_score,
        )
    except RagUnavailableError as exc:
        raise _unavailable(exc) from exc
    return ChatResponse.model_validate(result)


@router.post(
    "/search/code/index",
    response_model=CodeIndexJob,
    status_code=status.HTTP_202_ACCEPTED,
)
async def index_code(
    payload: CodeIndexRequest,
    request: Request,
    background: BackgroundTasks,
) -> CodeIndexJob:
    service = _service(request)
    if not service.available:
        raise _unavailable(RagUnavailableError())
    background.add_task(_run_index, service, payload.repository_ids, payload.force)
    return CodeIndexJob(
        status="started",
        message="indexing started",
        started_at=utcnow(),
    )


@router.get("/search/code/status", response_model=CodeIndexStatus)
async def code_search_status(request: Request) -> CodeIndexStatus:
    try:
        return await _service(request).status()
    except RagUnavailableError as exc:
        raise _unavailable(exc) from exc


__all__ = ["router"]
