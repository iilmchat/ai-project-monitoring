"""Repository endpoints: listing, status, refresh, compare and log."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.db.session import get_session
from app.git.command_backend import get_conflicts, get_worktree_diff
from app.git.pygit2_backend import (
    GitStatusError,
    compare_refs,
    read_commits,
    read_local_status,
)
from app.models.entities import ActionLog, Repository, RepositoryStatus
from app.schemas.action import (
    ActionLogResponse,
    ActionRequest,
    BulkActionRequest,
)
from app.schemas.ai import CommitMessageSuggestion
from app.schemas.ci import CIStatusResponse, ProviderCIStatus
from app.schemas.dependency import DependencyReport
from app.schemas.docker import DockerStatusResponse
from app.schemas.insights import InsightsReport
from app.schemas.mirror import (
    MirrorCandidatesResponse,
    MirrorPolicyUpdate,
    MirrorStatusResponse,
)
from app.schemas.recommendation import RecommendationResponse
from app.schemas.repository import (
    CommitInfoResponse,
    CompareResponse,
    RefreshRequest,
    RepositoryConflictsResponse,
    RepositoryListResponse,
    RepositoryRead,
    RepositoryStatusResponse,
)
from app.schemas.security import SecurityReport
from app.services.action_service import (
    ActionNotAllowedError,
    ActionService,
    ConfirmationRequiredError,
    UnknownActionError,
)
from app.services.bulk_service import BulkService
from app.services.ci_service import aggregate_ci
from app.services.compare_cache import CompareCache
from app.services.dependency_service import DependencyService
from app.services.docker_service import DockerService
from app.services.insights_service import InsightsService
from app.services.llm_service import LLMService
from app.services.mirror_service import MirrorService
from app.services.recommendation_service import generate_recommendations
from app.services.security_service import SecurityService
from app.services.status_service import StatusService

router = APIRouter(tags=["repositories"])


def _status_service(request: Request) -> StatusService:
    service: StatusService = request.app.state.status_service
    return service


def _compare_cache(request: Request) -> CompareCache:
    cache: CompareCache = request.app.state.compare_cache
    return cache


def _mirror_service(request: Request) -> MirrorService:
    service: MirrorService = request.app.state.mirror_service
    return service


def _docker_service(request: Request) -> DockerService:
    service: DockerService = request.app.state.docker_service
    return service


def _dependency_service(request: Request) -> DependencyService:
    service: DependencyService = request.app.state.dependency_service
    return service


def _security_service(request: Request) -> SecurityService:
    service: SecurityService = request.app.state.security_service
    return service


def _insights_service(request: Request) -> InsightsService:
    service: InsightsService = request.app.state.insights_service
    return service


def _llm_service(request: Request) -> LLMService:
    service: LLMService = request.app.state.llm_service
    return service


def _action_service(request: Request) -> ActionService:
    service: ActionService = request.app.state.action_service
    return service


def _bulk_service(request: Request) -> BulkService:
    service: BulkService = request.app.state.bulk_service
    return service


def _aggregate_ci(results: list[dict[str, object]]) -> str:
    return aggregate_ci(results)


@router.get("/repositories/{repository_id}/ci-status", response_model=CIStatusResponse)
async def repository_ci_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CIStatusResponse:
    repository = await _get_repository(session, repository_id)
    status_row = await session.scalar(
        select(RepositoryStatus).where(
            RepositoryStatus.repository_id == repository_id
        )
    )
    branch = status_row.branch if status_row is not None and status_row.branch else "main"

    async def lookup(full_name: str | None, provider: str) -> dict[str, object]:
        if full_name is None:
            return {
                "provider": provider,
                "status": "not_configured",
                "conclusion": None,
                "url": None,
            }
        client = (
            request.app.state.github_client
            if provider == "github"
            else request.app.state.gitflic_client
        )
        result: dict[str, object] = await client.get_ci_status(full_name, branch)
        return result

    github, gitflic = await asyncio.gather(
        lookup(repository.github_full_name, "github"),
        lookup(repository.gitflic_full_name, "gitflic"),
    )
    return CIStatusResponse(
        repository_id=repository_id,
        branch=branch,
        github=ProviderCIStatus.model_validate(github),
        gitflic=ProviderCIStatus.model_validate(gitflic),
        aggregate=_aggregate_ci([github, gitflic]),
    )


async def _get_repository(session: AsyncSession, repository_id: int) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"repository {repository_id} not found",
        )
    return repository


@router.get(
    "/repositories/{repository_id}/docker",
    response_model=DockerStatusResponse,
)
async def repository_docker_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
) -> DockerStatusResponse:
    repository = await _get_repository(session, repository_id)
    result = await _docker_service(request).get_container_status(
        repository.path,
        refresh=refresh,
    )
    return DockerStatusResponse(
        repository_id=repository_id,
        checked_at=utcnow(),
        **result.model_dump(),
    )


@router.get(
    "/repositories/{repository_id}/dependencies",
    response_model=DependencyReport,
)
async def repository_dependencies(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
    ecosystem: Annotated[Literal["python", "node", "all"] | None, Query()] = None,
) -> DependencyReport:
    repository = await _get_repository(session, repository_id)
    return await _dependency_service(request).get_report(
        repository.id,
        repository.path,
        ecosystem=ecosystem,
        refresh=refresh,
    )


@router.get(
    "/repositories/{repository_id}/security",
    response_model=SecurityReport,
)
async def repository_security(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
    include_secrets: Annotated[bool, Query()] = True,
    min_severity: Annotated[
        Literal["critical", "high", "medium", "low", "all"], Query()
    ] = "high",
) -> SecurityReport:
    repository = await _get_repository(session, repository_id)
    return await _security_service(request).get_report(
        repository.id,
        repository.path,
        refresh=refresh,
        include_secrets=include_secrets,
        min_severity=min_severity,
    )


@router.get(
    "/repositories/{repository_id}/insights",
    response_model=InsightsReport,
)
async def repository_insights(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    refresh: Annotated[bool, Query()] = False,
) -> InsightsReport:
    repository = await _get_repository(session, repository_id)
    return await _insights_service(request).get_report(
        repository.id,
        repository.path,
        days=days,
        refresh=refresh,
    )


def _count_diff_files(diff: str) -> int:
    return sum(1 for line in diff.splitlines() if line.startswith("diff --git "))


@router.post(
    "/repositories/{repository_id}/ai/commit-message",
    response_model=CommitMessageSuggestion,
)
async def generate_commit_message(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommitMessageSuggestion:
    repository = await _get_repository(session, repository_id)
    service = _llm_service(request)
    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="llm_disabled",
        )
    if not service.remote_allowed():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="llm_remote_not_allowed",
        )

    diff_result = await asyncio.to_thread(
        get_worktree_diff, repository.path, 10
    )
    if not diff_result.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=diff_result.error or "git_diff_failed",
        )
    if not diff_result.stdout.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет изменений для коммита",
        )

    original = diff_result.stdout
    max_chars = max(int(request.app.state.settings.llm_max_diff_chars), 100)
    truncated = len(original) > max_chars
    prepared = original
    warnings: list[str] = []
    if truncated:
        prepared = f"{original[:max_chars]}\n[diff truncated]"
        warnings.append("diff_truncated")

    message = await service.generate_commit_message(prepared)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM недоступна. Проверьте настройки.",
        )

    return CommitMessageSuggestion(
        repository_id=repository_id,
        message=message,
        provider=service.provider,
        model=service.model,
        truncated=truncated,
        diff_chars=len(original),
        files_changed=_count_diff_files(original),
        warnings=warnings,
        generated_at=utcnow(),
    )


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    session: Annotated[AsyncSession, Depends(get_session)],
    tracked: Annotated[bool | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> RepositoryListResponse:
    filters = []
    if tracked is not None:
        filters.append(Repository.tracked.is_(tracked))

    total = await session.scalar(select(func.count()).select_from(Repository).where(*filters))
    result = await session.scalars(
        select(Repository).where(*filters).order_by(Repository.path).offset(skip).limit(limit)
    )
    items = [RepositoryRead.model_validate(item) for item in result.all()]

    return RepositoryListResponse(
        items=items,
        total=total or 0,
        skip=skip,
        limit=limit,
    )


@router.post("/repositories/{repository_id}/track", response_model=RepositoryRead)
async def track_repository(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    repository.tracked = True
    await session.commit()
    await session.refresh(repository)
    return RepositoryRead.model_validate(repository)


@router.post("/repositories/{repository_id}/untrack", response_model=RepositoryRead)
async def untrack_repository(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    repository.tracked = False
    await session.commit()
    await session.refresh(repository)
    return RepositoryRead.model_validate(repository)


@router.get("/repositories/{repository_id}/status", response_model=RepositoryStatusResponse)
async def get_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    fetch: Annotated[bool, Query()] = True,
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).get_status(
        session, repository, use_cache=True, fetch=fetch
    )
    return RepositoryStatusResponse.model_validate(snapshot)


@router.post("/repositories/{repository_id}/refresh", response_model=RepositoryStatusResponse)
async def refresh_repository_status(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: RefreshRequest | None = None,
) -> RepositoryStatusResponse:
    repository = await _get_repository(session, repository_id)
    should_fetch = payload.fetch if payload is not None else True
    snapshot = await _status_service(request).refresh(session, repository, fetch=should_fetch)
    _compare_cache(request).invalidate(repository_id)
    return RepositoryStatusResponse.model_validate(snapshot)


@router.get(
    "/repositories/{repository_id}/recommendations",
    response_model=list[RecommendationResponse],
)
async def repository_recommendations(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RecommendationResponse]:
    repository = await _get_repository(session, repository_id)
    snapshot = await _status_service(request).get_status(
        session, repository, use_cache=True, fetch=False
    )
    status_response = RepositoryStatusResponse.model_validate(snapshot)
    return [
        RecommendationResponse.model_validate(item)
        for item in generate_recommendations(status_response)
    ]


@router.get("/repositories/{repository_id}/compare", response_model=CompareResponse)
async def compare_repository(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    base: Annotated[str | None, Query()] = None,
    head: Annotated[str | None, Query()] = None,
) -> CompareResponse:
    repository = await _get_repository(session, repository_id)

    resolved_base = base
    if resolved_base is None:
        try:
            local = await asyncio.to_thread(read_local_status, repository.path)
        except GitStatusError:
            return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])
        resolved_base = local.upstream

    if resolved_base is None:
        return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])

    resolved_head = head or "HEAD"
    cache = _compare_cache(request)
    cached = cache.get(repository.id, resolved_base, resolved_head)
    if cached is not None:
        return CompareResponse.model_validate(cached)

    try:
        result = await asyncio.to_thread(
            compare_refs,
            repository.path,
            resolved_base,
            resolved_head,
            10,
        )
    except GitStatusError:
        return CompareResponse(ahead=0, behind=0, status="unavailable", commits=[])

    cache.set(repository.id, resolved_base, resolved_head, result)
    return CompareResponse.model_validate(result)


@router.get("/repositories/{repository_id}/mirror", response_model=MirrorStatusResponse)
async def get_repository_mirror(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh: Annotated[bool, Query()] = False,
) -> MirrorStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _mirror_service(request).get_mirror_status(
        repository, refresh=refresh
    )
    return MirrorStatusResponse.model_validate(snapshot)


@router.post(
    "/repositories/{repository_id}/mirror/refresh",
    response_model=MirrorStatusResponse,
)
async def refresh_repository_mirror(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MirrorStatusResponse:
    repository = await _get_repository(session, repository_id)
    snapshot = await _mirror_service(request).refresh_mirror_status(repository)
    return MirrorStatusResponse.model_validate(snapshot)


@router.patch(
    "/repositories/{repository_id}/mirror-policy",
    response_model=RepositoryRead,
)
async def update_mirror_policy(
    repository_id: int,
    payload: MirrorPolicyUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryRead:
    repository = await _get_repository(session, repository_id)
    if payload.canonical_provider is not None:
        repository.canonical_provider = payload.canonical_provider
    if payload.mirror_expected is not None:
        repository.mirror_expected = payload.mirror_expected
    if payload.mirror_policy is not None:
        repository.mirror_policy = payload.mirror_policy
    if payload.github_full_name is not None:
        repository.github_full_name = payload.github_full_name.strip() or None
    if payload.gitflic_full_name is not None:
        repository.gitflic_full_name = payload.gitflic_full_name.strip() or None
    await session.commit()
    await session.refresh(repository)
    await _mirror_service(request).invalidate(repository_id)
    return RepositoryRead.model_validate(repository)


@router.get("/mirror/candidates", response_model=MirrorCandidatesResponse)
async def mirror_candidates(request: Request) -> MirrorCandidatesResponse:
    candidates = await _mirror_service(request).discover_candidates()
    return MirrorCandidatesResponse.model_validate(candidates)


@router.post(
    "/repositories/{repository_id}/actions/{action}",
    response_model=ActionLogResponse,
)
async def run_repository_action(
    repository_id: int,
    action: str,
    payload: ActionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionLogResponse:
    repository = await _get_repository(session, repository_id)
    try:
        entry = await _action_service(request).execute_action(
            session,
            repository,
            action,
            confirm=payload.confirm,
            message=payload.message,
        )
    except UnknownActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ConfirmationRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ActionNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if entry.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=entry.error or entry.output or "action failed",
        )
    return ActionLogResponse.model_validate(entry)


@router.get(
    "/repositories/{repository_id}/actions",
    response_model=list[ActionLogResponse],
)
async def repository_action_history(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[ActionLogResponse]:
    await _get_repository(session, repository_id)
    rows = (
        await session.scalars(
            select(ActionLog)
            .where(ActionLog.repository_id == repository_id)
            .order_by(ActionLog.created_at.desc(), ActionLog.id.desc())
            .limit(limit)
        )
    ).all()
    return [ActionLogResponse.model_validate(row) for row in rows]


@router.post("/mirror/actions/{action}", response_model=ActionLogResponse)
async def run_mirror_action(
    action: str,
    payload: ActionRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionLogResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm=true is required for mutations",
        )
    if payload.repository_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_id is required for mirror actions",
        )
    repository = await _get_repository(session, payload.repository_id)
    try:
        entry = await _action_service(request).execute_action(
            session, repository, action, confirm=payload.confirm
        )
    except (UnknownActionError, ActionNotAllowedError, ConfirmationRequiredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if entry.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=entry.error or entry.output or "action failed",
        )
    return ActionLogResponse.model_validate(entry)


@router.post("/repositories/actions/fetch_all", status_code=status.HTTP_202_ACCEPTED)
async def bulk_fetch_all(
    request: Request,
    background_tasks: BackgroundTasks,
    tracked_only: Annotated[bool, Query()] = True,
    payload: BulkActionRequest | None = None,
) -> dict[str, object]:
    repo_ids = payload.repo_ids if payload is not None else None
    background_tasks.add_task(
        _bulk_service(request).fetch_all, tracked_only, repo_ids
    )
    return {
        "status": "accepted",
        "action": "fetch_all",
        "tracked_only": tracked_only,
        "repo_ids": repo_ids,
    }


@router.post(
    "/repositories/actions/sync_mirrors_all",
    status_code=status.HTTP_202_ACCEPTED,
)
async def bulk_sync_mirrors(
    request: Request,
    background_tasks: BackgroundTasks,
    tracked_only: Annotated[bool, Query()] = True,
    payload: BulkActionRequest | None = None,
) -> dict[str, object]:
    repo_ids = payload.repo_ids if payload is not None else None
    background_tasks.add_task(
        _bulk_service(request).sync_mirrors_all, tracked_only, repo_ids
    )
    return {
        "status": "accepted",
        "action": "sync_mirrors_all",
        "tracked_only": tracked_only,
        "repo_ids": repo_ids,
    }


@router.post(
    "/repositories/actions/migrate_to_gitflic",
    status_code=status.HTTP_202_ACCEPTED,
)
async def bulk_migrate_to_gitflic(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    background_tasks.add_task(_bulk_service(request).migrate_to_gitflic)
    return {"status": "accepted", "action": "migrate_to_gitflic"}


@router.get("/repositories/export")
async def export_repositories(
    session: Annotated[AsyncSession, Depends(get_session)],
    format: Annotated[Literal["csv", "json"], Query()] = "json",
) -> Response:
    repositories = (
        await session.scalars(
            select(Repository)
            .options(selectinload(Repository.status), selectinload(Repository.mirror))
            .order_by(Repository.path)
        )
    ).all()

    rows = [
        {
            "id": repository.id,
            "path": repository.path,
            "alias": repository.alias,
            "tracked": repository.tracked,
            "state": repository.status.state if repository.status else None,
            "branch": repository.status.branch if repository.status else None,
            "ahead": repository.status.ahead if repository.status else None,
            "behind": repository.status.behind if repository.status else None,
            "remote_status": repository.status.remote_status if repository.status else None,
            "canonical_provider": repository.canonical_provider,
            "mirror_status": repository.mirror.mirror_status if repository.mirror else None,
        }
        for repository in repositories
    ]

    if format == "json":
        return Response(
            content=json.dumps(rows, ensure_ascii=False, default=str),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="repositories.json"'},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["id"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="repositories.csv"'},
    )


@router.get(
    "/repositories/{repository_id}/conflicts",
    response_model=RepositoryConflictsResponse,
)
async def repository_conflicts(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryConflictsResponse:
    repository = await _get_repository(session, repository_id)
    files = await asyncio.to_thread(get_conflicts, repository.path)
    return RepositoryConflictsResponse(repository_id=repository_id, files=files)


@router.get("/repositories/{repository_id}/log", response_model=list[CommitInfoResponse])
async def repository_log(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[CommitInfoResponse]:
    repository = await _get_repository(session, repository_id)
    try:
        commits = await asyncio.to_thread(read_commits, repository.path, "HEAD", limit)
    except GitStatusError:
        return []
    return [CommitInfoResponse.model_validate(commit) for commit in commits]
