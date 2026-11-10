"""Repository endpoints: listing, status, refresh, compare and log."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
from pathlib import Path
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

from app.core.metrics import observe_ai_cache, observe_llm_call
from app.db.base import utcnow
from app.db.session import get_session
from app.git.command_backend import (
    get_conflicts,
    get_staged_diff,
    get_worktree_diff,
    list_tags,
    log_between,
    ref_exists,
)
from app.git.pygit2_backend import (
    GitStatusError,
    compare_refs,
    read_commits,
    read_local_status,
)
from app.models.entities import ActionLog, AICache, Repository, RepositoryStatus
from app.schemas.action import (
    ActionLogResponse,
    ActionRequest,
    BulkActionRequest,
    BulkDependencyUpdateRequest,
    DependencyUpdateRequest,
)
from app.schemas.ai import (
    AgentTask,
    AgentTaskRequest,
    CodeReviewRequest,
    CodeReviewResponse,
    CommitMessageSuggestion,
    ConflictResolveRequest,
    ConflictResolveResponse,
    CveExplainRequest,
    CveExplanation,
    ReleaseNotesRequest,
    ReleaseNotesResponse,
)
from app.schemas.ci import CIStatusResponse, ProviderCIStatus
from app.schemas.dependency import DependencyReport
from app.schemas.docker import DockerStatusResponse
from app.schemas.docs import ReadmeResponse, RepositoryDocResponse
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
    RepositoryTagsResponse,
)
from app.schemas.security import SecurityReport
from app.services.action_service import (
    ActionNotAllowedError,
    ActionService,
    ConfirmationRequiredError,
    UnknownActionError,
)
from app.services.agent_task_service import (
    AgentTaskService,
    AgentTaskUnavailableError,
)
from app.services.ai_cache import build_cache_key, cache_is_fresh, cache_lock
from app.services.bulk_service import BulkService
from app.services.ci_service import aggregate_ci
from app.services.compare_cache import CompareCache
from app.services.dependency_service import DependencyService
from app.services.dependency_update_service import (
    DependencyUpdateError,
    DependencyUpdateService,
)
from app.services.docker_service import DockerService
from app.services.insights_service import InsightsService
from app.services.llm_service import LLMService
from app.services.mirror_service import MirrorService
from app.services.readme_service import (
    DocumentAccessError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    read_document,
    read_readme,
)
from app.services.recommendation_service import generate_recommendations
from app.services.secret_scanner import redact_secrets
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


def _dependency_update_service(request: Request) -> DependencyUpdateService:
    service: DependencyUpdateService = request.app.state.dependency_update_service
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
    "/repositories/{repository_id}/readme",
    response_model=ReadmeResponse,
)
async def repository_readme(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReadmeResponse:
    repository = await _get_repository(session, repository_id)
    try:
        readme = read_readme(Path(repository.path))
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DocumentAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if readme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="README not found",
        )
    return ReadmeResponse(
        repository_id=repository_id,
        path=readme.path,
        name=readme.name,
        version=readme.version,
        content=readme.content,
    )


@router.get(
    "/repositories/{repository_id}/docs",
    response_model=RepositoryDocResponse,
)
async def repository_document(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    path: Annotated[str, Query(min_length=1, max_length=2048)],
) -> RepositoryDocResponse:
    repository = await _get_repository(session, repository_id)
    try:
        document = read_document(Path(repository.path), path)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except DocumentAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RepositoryDocResponse(
        repository_id=repository_id,
        path=document.path,
        content=document.content,
    )


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
    ecosystem: Annotated[
        Literal["python", "node", "dotnet", "all"] | None, Query()
    ] = None,
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
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommitMessageSuggestion:
    repository = await _get_repository(session, repository_id)
    service = _llm_service(request)
    ok, error = await service.availability()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error or "llm_disabled",
        )
    config = await service.resolve()

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
    files_changed = _count_diff_files(original)

    try:
        local = await asyncio.to_thread(read_local_status, repository.path)
        branch = local.branch
    except GitStatusError:
        branch = None
    state = {
        "diff_sha": hashlib.sha256(prepared.encode("utf-8")).hexdigest(),
        "branch": branch,
    }
    prompt_version = request.app.state.settings.ai_prompt_version
    cache_key = build_cache_key(
        "commit-message",
        str(repository_id),
        state,
        config.model,
        prompt_version,
    )
    ttl = int(request.app.state.settings.ai_cache_ttl_seconds)
    row = await session.get(AICache, cache_key)
    if row is not None and cache_is_fresh(row.checked_at, ttl):
        payload = row.payload if isinstance(row.payload, dict) else {}
        cached_message = payload.get("message")
        if isinstance(cached_message, str) and cached_message:
            observe_ai_cache("commit_message", hit=True)
            response.headers["X-AI-Cache"] = "hit"
            return _cached_commit_suggestion(
                repository_id,
                cached_message,
                payload,
                config.provider,
                row.model or config.model,
            )

    lock = cache_lock(cache_key)
    async with lock:
        row = await session.get(AICache, cache_key)
        if row is not None and cache_is_fresh(row.checked_at, ttl):
            payload = row.payload if isinstance(row.payload, dict) else {}
            cached_message = payload.get("message")
            if isinstance(cached_message, str) and cached_message:
                observe_ai_cache("commit_message", hit=True)
                response.headers["X-AI-Cache"] = "hit"
                return _cached_commit_suggestion(
                    repository_id,
                    cached_message,
                    payload,
                    config.provider,
                    row.model or config.model,
                )

        observe_ai_cache("commit_message", hit=False)
        message = await service.generate_commit_message(prepared)
        observe_llm_call(
            "commit_message",
            config.provider,
            "ok" if message is not None else "error",
        )
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM недоступна. Проверьте настройки.",
            )

        payload = {
            "message": message,
            "truncated": truncated,
            "diff_chars": len(original),
            "files_changed": files_changed,
            "warnings": warnings,
        }
        if row is None:
            row = AICache(
                key=cache_key,
                kind="commit_message",
                model=config.model,
            )
            session.add(row)
        row.payload = payload
        row.checked_at = utcnow()
        await session.commit()

    response.headers["X-AI-Cache"] = "miss"
    return CommitMessageSuggestion(
        repository_id=repository_id,
        message=message,
        provider=config.provider,
        model=config.model,
        truncated=truncated,
        diff_chars=len(original),
        files_changed=files_changed,
        warnings=warnings,
        cached=False,
        generated_at=utcnow(),
    )


def _cached_commit_suggestion(
    repository_id: int,
    message: str,
    payload: dict[str, object],
    provider: str,
    model: str,
) -> CommitMessageSuggestion:
    warnings = payload.get("warnings")
    return CommitMessageSuggestion(
        repository_id=repository_id,
        message=message,
        provider=provider,
        model=model,
        truncated=bool(payload.get("truncated", False)),
        diff_chars=_payload_int(payload.get("diff_chars")),
        files_changed=_payload_int(payload.get("files_changed")),
        warnings=[str(item) for item in warnings] if isinstance(warnings, list) else [],
        cached=True,
        generated_at=utcnow(),
    )


def _payload_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _safe_repository_file(
    repository_path: str,
    file_path: str,
    *,
    max_bytes: int,
) -> Path:
    """Resolve ``file_path`` inside the repository and reject traversal."""
    root = Path(repository_path).resolve()
    raw = Path(file_path)
    if raw.is_absolute():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path_outside_repository",
        )
    try:
        candidate = (root / raw).resolve()
        relative = candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path_outside_repository",
        ) from exc
    if ".git" in relative.parts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path_outside_repository",
        )
    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file_not_found",
        )
    if candidate.stat().st_size > max(max_bytes, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_too_large",
        )
    return candidate


def _find_conflict_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return ``(start, end)`` line indexes for ``<<<<<<<`` … ``>>>>>>>``."""
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for index, line in enumerate(lines):
        marker = line.lstrip()
        if marker.startswith("<<<<<<<"):
            start = index
        elif marker.startswith(">>>>>>>") and start is not None:
            blocks.append((start, index))
            start = None
    return blocks


def _assemble_conflict_file(
    lines: list[str],
    blocks: list[tuple[int, int]],
    merged: list[str],
) -> str:
    """Replace processed conflict blocks with merged code, keep the rest."""
    output: list[str] = []
    cursor = 0
    for (start, end), code in zip(blocks, merged, strict=False):
        output.extend(lines[cursor:start])
        output.append(code)
        if code and not code.endswith("\n"):
            output.append("\n")
        cursor = end + 1
    output.extend(lines[cursor:])
    return "".join(output)


def _cached_conflict_blocks(
    row: AICache | None,
    ttl: int,
    expected: int,
) -> list[str] | None:
    if row is None or not cache_is_fresh(row.checked_at, ttl):
        return None
    payload = row.payload if isinstance(row.payload, dict) else {}
    merged = payload.get("merged")
    if (
        not isinstance(merged, list)
        or len(merged) != expected
        or not all(isinstance(item, str) for item in merged)
    ):
        return None
    return [str(item) for item in merged]


def _cached_release_notes(
    repository_id: int,
    row: AICache | None,
    ttl: int,
    from_tag: str,
    to_tag: str,
    provider: str,
    model: str,
) -> ReleaseNotesResponse | None:
    if row is None or not cache_is_fresh(row.checked_at, ttl):
        return None
    payload = row.payload if isinstance(row.payload, dict) else {}
    changelog = payload.get("changelog")
    if not isinstance(changelog, str) or not changelog:
        return None
    warnings = payload.get("warnings")
    return ReleaseNotesResponse(
        repository_id=repository_id,
        from_tag=from_tag,
        to_tag=to_tag,
        changelog=changelog,
        commits=_payload_int(payload.get("commits")),
        provider=provider,
        model=row.model or model,
        truncated=bool(payload.get("truncated", False)),
        warnings=[str(item) for item in warnings] if isinstance(warnings, list) else [],
        cached=True,
        generated_at=utcnow(),
    )


def _valid_ref(ref: str) -> bool:
    if not ref or ref.startswith("-") or ".." in ref:
        return False
    return re.fullmatch(r"[A-Za-z0-9._/-]+", ref) is not None


@router.post(
    "/repositories/{repository_id}/ai/code-review",
    response_model=CodeReviewResponse,
)
async def review_repository_code(
    repository_id: int,
    payload: CodeReviewRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CodeReviewResponse:
    repository = await _get_repository(session, repository_id)
    service = _llm_service(request)
    ok, error = await service.availability()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error or "llm_disabled",
        )
    config = await service.resolve()

    diff_result = await asyncio.to_thread(
        get_worktree_diff, repository.path, 10
    )
    original = diff_result.stdout if diff_result.ok else ""
    if not original.strip():
        staged_result = await asyncio.to_thread(
            get_staged_diff, repository.path, 10
        )
        if staged_result.ok and staged_result.stdout.strip():
            original = staged_result.stdout
    if not original.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет изменений",
        )

    settings = request.app.state.settings
    max_chars = max(int(settings.ai_code_review_max_chars), 100)
    truncated = len(original) > max_chars
    prepared = original
    warnings: list[str] = []
    if truncated:
        prepared = f"{original[:max_chars]}\n[diff truncated]"
        warnings.append("diff_truncated")
    prepared = redact_secrets(prepared)
    files_reviewed = _count_diff_files(original)

    state = {
        "diff_sha": hashlib.sha256(prepared.encode("utf-8")).hexdigest(),
        "language": payload.language,
    }
    prompt_version = settings.ai_prompt_version
    cache_key = build_cache_key(
        "code-review",
        str(repository_id),
        state,
        config.model,
        prompt_version,
    )
    ttl = int(settings.ai_cache_ttl_seconds)

    if not payload.refresh:
        row = await session.get(AICache, cache_key)
        cached = _cached_code_review_from_row(
            repository_id, row, ttl, config.provider, config.model
        )
        if cached is not None:
            observe_ai_cache("code_review", hit=True)
            response.headers["X-AI-Cache"] = "hit"
            return cached

    lock = cache_lock(cache_key)
    async with lock:
        if not payload.refresh:
            row = await session.get(AICache, cache_key)
            cached = _cached_code_review_from_row(
                repository_id, row, ttl, config.provider, config.model
            )
            if cached is not None:
                observe_ai_cache("code_review", hit=True)
                response.headers["X-AI-Cache"] = "hit"
                return cached

        observe_ai_cache("code_review", hit=False)
        review = await service.review_code(prepared, language=payload.language)
        observe_llm_call(
            "code_review",
            config.provider,
            "ok" if review is not None else "error",
        )
        if review is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM недоступна. Проверьте настройки.",
            )

        cached_payload = {
            "review": review,
            "truncated": truncated,
            "diff_chars": len(original),
            "files_reviewed": files_reviewed,
            "warnings": warnings,
        }
        row = await session.get(AICache, cache_key)
        if row is None:
            row = AICache(
                key=cache_key,
                kind="code_review",
                model=config.model,
            )
            session.add(row)
        row.payload = cached_payload
        row.checked_at = utcnow()
        await session.commit()

    response.headers["X-AI-Cache"] = "miss"
    return CodeReviewResponse(
        repository_id=repository_id,
        review=review,
        provider=config.provider,
        model=config.model,
        files_reviewed=files_reviewed,
        diff_chars=len(original),
        truncated=truncated,
        warnings=warnings,
        cached=False,
        generated_at=utcnow(),
    )


def _cached_code_review_from_row(
    repository_id: int,
    row: AICache | None,
    ttl: int,
    provider: str,
    model: str,
) -> CodeReviewResponse | None:
    if row is None or not cache_is_fresh(row.checked_at, ttl):
        return None
    payload = row.payload if isinstance(row.payload, dict) else {}
    review = payload.get("review")
    if not isinstance(review, str) or not review:
        return None
    warnings = payload.get("warnings")
    return CodeReviewResponse(
        repository_id=repository_id,
        review=review,
        provider=provider,
        model=row.model or model,
        files_reviewed=_payload_int(payload.get("files_reviewed")),
        diff_chars=_payload_int(payload.get("diff_chars")),
        truncated=bool(payload.get("truncated", False)),
        warnings=[str(item) for item in warnings] if isinstance(warnings, list) else [],
        cached=True,
        generated_at=utcnow(),
    )


@router.post(
    "/repositories/{repository_id}/ai/resolve-conflict",
    response_model=ConflictResolveResponse,
)
async def resolve_repository_conflict(
    repository_id: int,
    payload: ConflictResolveRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConflictResolveResponse:
    repository = await _get_repository(session, repository_id)
    service = _llm_service(request)
    ok, error = await service.availability()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error or "llm_disabled",
        )
    config = await service.resolve()
    settings = request.app.state.settings

    path = _safe_repository_file(
        repository.path,
        payload.file_path,
        max_bytes=int(settings.ai_conflict_max_file_bytes),
    )
    data = await asyncio.to_thread(path.read_bytes)
    if b"\x00" in data[:8192]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binary_file",
        )
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    blocks = _find_conflict_blocks(lines)
    if not blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Конфликтов не найдено",
        )

    max_blocks = max(int(settings.ai_conflict_max_blocks), 1)
    max_chars = max(int(settings.ai_conflict_max_chars), 100)
    selected: list[tuple[int, int]] = []
    total = 0
    for start, end in blocks:
        block_text = "".join(lines[start : end + 1])
        if len(selected) >= max_blocks or total + len(block_text) > max_chars:
            break
        selected.append((start, end))
        total += len(block_text)
    if not selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Конфликт слишком большой",
        )

    truncated = len(blocks) > len(selected)
    warnings = ["verify_before_apply"]
    if truncated:
        warnings.append("conflict_truncated")

    block_text = "\n".join(
        "".join(lines[start : end + 1]) for start, end in selected
    )
    state = {
        "file_path": payload.file_path,
        "blocks_sha": hashlib.sha256(block_text.encode("utf-8")).hexdigest(),
        "language": payload.language,
    }
    cache_key = build_cache_key(
        "resolve-conflict",
        str(repository_id),
        state,
        config.model,
        settings.ai_prompt_version,
    )
    ttl = int(settings.ai_cache_ttl_seconds)

    if not payload.refresh:
        row = await session.get(AICache, cache_key)
        cached_merged = _cached_conflict_blocks(row, ttl, len(selected))
        if cached_merged is not None:
            observe_ai_cache("conflict_resolve", hit=True)
            response.headers["X-AI-Cache"] = "hit"
            return ConflictResolveResponse(
                repository_id=repository_id,
                file_path=payload.file_path,
                resolved=_assemble_conflict_file(lines, selected, cached_merged),
                blocks=len(cached_merged),
                provider=config.provider,
                model=row.model if row is not None else config.model,
                truncated=truncated,
                warnings=warnings,
                cached=True,
                generated_at=utcnow(),
            )

    lock = cache_lock(cache_key)
    async with lock:
        if not payload.refresh:
            row = await session.get(AICache, cache_key)
            cached_merged = _cached_conflict_blocks(row, ttl, len(selected))
            if cached_merged is not None:
                observe_ai_cache("conflict_resolve", hit=True)
                response.headers["X-AI-Cache"] = "hit"
                return ConflictResolveResponse(
                    repository_id=repository_id,
                    file_path=payload.file_path,
                    resolved=_assemble_conflict_file(lines, selected, cached_merged),
                    blocks=len(cached_merged),
                    provider=config.provider,
                    model=row.model if row is not None else config.model,
                    truncated=truncated,
                    warnings=warnings,
                    cached=True,
                    generated_at=utcnow(),
                )

        observe_ai_cache("conflict_resolve", hit=False)
        merged_blocks: list[str] = []
        for start, end in selected:
            merged_block = await service.resolve_conflict(
                "".join(lines[start : end + 1]),
                language=payload.language,
            )
            if merged_block is None:
                observe_llm_call("conflict_resolve", config.provider, "error")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="LLM недоступна. Проверьте настройки.",
                )
            merged_blocks.append(merged_block)
        observe_llm_call("conflict_resolve", config.provider, "ok")

        row = await session.get(AICache, cache_key)
        if row is None:
            row = AICache(
                key=cache_key,
                kind="conflict_resolve",
                model=config.model,
            )
            session.add(row)
        row.payload = {"merged": merged_blocks}
        row.checked_at = utcnow()
        await session.commit()

    response.headers["X-AI-Cache"] = "miss"
    return ConflictResolveResponse(
        repository_id=repository_id,
        file_path=payload.file_path,
        resolved=_assemble_conflict_file(lines, selected, merged_blocks),
        blocks=len(merged_blocks),
        provider=config.provider,
        model=config.model,
        truncated=truncated,
        warnings=warnings,
        cached=False,
        generated_at=utcnow(),
    )


@router.post(
    "/repositories/{repository_id}/ai/release-notes",
    response_model=ReleaseNotesResponse,
)
async def generate_repository_release_notes(
    repository_id: int,
    payload: ReleaseNotesRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReleaseNotesResponse:
    repository = await _get_repository(session, repository_id)
    service = _llm_service(request)
    ok, error = await service.availability()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error or "llm_disabled",
        )
    config = await service.resolve()
    settings = request.app.state.settings

    from_tag = payload.from_tag.strip()
    to_tag = payload.to_tag.strip() or "HEAD"
    if not _valid_ref(from_tag) or not _valid_ref(to_tag):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_range",
        )
    if not await asyncio.to_thread(ref_exists, repository.path, from_tag):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tag_not_found:{from_tag}",
        )
    if not await asyncio.to_thread(ref_exists, repository.path, to_tag):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tag_not_found:{to_tag}",
        )

    max_commits = max(int(settings.ai_release_notes_max_commits), 1)
    log_result = await asyncio.to_thread(
        log_between,
        repository.path,
        from_tag,
        to_tag,
        limit=max_commits,
    )
    if not log_result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=log_result.error or "git_log_failed",
        )
    commits_text = log_result.stdout.strip()
    if not commits_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет коммитов",
        )

    max_chars = max(int(settings.ai_release_notes_max_chars), 100)
    truncated = len(commits_text) > max_chars
    prepared = commits_text
    warnings: list[str] = []
    if truncated:
        prepared = f"{commits_text[:max_chars]}\n[commits truncated]"
        warnings.append("commits_truncated")
    commits_count = len(commits_text.splitlines())
    if commits_count >= max_commits:
        truncated = True
        if "commits_truncated" not in warnings:
            warnings.append("commits_truncated")

    state = {
        "from_tag": from_tag,
        "to_tag": to_tag,
        "commits_sha": hashlib.sha256(prepared.encode("utf-8")).hexdigest(),
        "language": payload.language,
    }
    cache_key = build_cache_key(
        "release-notes",
        str(repository_id),
        state,
        config.model,
        settings.ai_prompt_version,
    )
    ttl = int(settings.ai_cache_ttl_seconds)

    if not payload.refresh:
        row = await session.get(AICache, cache_key)
        cached = _cached_release_notes(
            repository_id,
            row,
            ttl,
            from_tag,
            to_tag,
            config.provider,
            config.model,
        )
        if cached is not None:
            observe_ai_cache("release_notes", hit=True)
            response.headers["X-AI-Cache"] = "hit"
            return cached

    lock = cache_lock(cache_key)
    async with lock:
        if not payload.refresh:
            row = await session.get(AICache, cache_key)
            cached = _cached_release_notes(
                repository_id,
                row,
                ttl,
                from_tag,
                to_tag,
                config.provider,
                config.model,
            )
            if cached is not None:
                observe_ai_cache("release_notes", hit=True)
                response.headers["X-AI-Cache"] = "hit"
                return cached

        observe_ai_cache("release_notes", hit=False)
        changelog = await service.generate_release_notes(
            prepared,
            language=payload.language,
        )
        observe_llm_call(
            "release_notes",
            config.provider,
            "ok" if changelog is not None else "error",
        )
        if changelog is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM недоступна. Проверьте настройки.",
            )

        row = await session.get(AICache, cache_key)
        if row is None:
            row = AICache(
                key=cache_key,
                kind="release_notes",
                model=config.model,
            )
            session.add(row)
        row.payload = {
            "changelog": changelog,
            "commits": commits_count,
            "truncated": truncated,
            "warnings": warnings,
        }
        row.checked_at = utcnow()
        await session.commit()

    response.headers["X-AI-Cache"] = "miss"
    return ReleaseNotesResponse(
        repository_id=repository_id,
        from_tag=from_tag,
        to_tag=to_tag,
        changelog=changelog,
        commits=commits_count,
        provider=config.provider,
        model=config.model,
        truncated=truncated,
        warnings=warnings,
        cached=False,
        generated_at=utcnow(),
    )


@router.post(
    "/repositories/{repository_id}/ai/cve-explain",
    response_model=CveExplanation,
)
async def explain_repository_cve(
    repository_id: int,
    payload: CveExplainRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CveExplanation:
    await _get_repository(session, repository_id)
    service = _llm_service(request)
    ok, error = await service.availability()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error or "llm_disabled",
        )
    config = await service.resolve()

    cve_id = payload.cve_id.strip()
    state = {"cve_id": cve_id, "summary": payload.summary}
    cache_key = build_cache_key(
        "cve-explain",
        cve_id,
        state,
        config.model,
        request.app.state.settings.ai_prompt_version,
    )
    ttl = int(request.app.state.settings.ai_cache_ttl_seconds)
    row = await session.get(AICache, cache_key)
    if row is not None and cache_is_fresh(row.checked_at, ttl):
        explanation = (
            row.payload.get("explanation")
            if isinstance(row.payload, dict)
            else None
        )
        if isinstance(explanation, str) and explanation:
            observe_ai_cache("cve_explain", hit=True)
            response.headers["X-AI-Cache"] = "hit"
            return CveExplanation(
                explanation=explanation,
                cached=True,
                model=row.model,
                generated_at=utcnow(),
            )

    lock = cache_lock(cache_key)
    async with lock:
        row = await session.get(AICache, cache_key)
        if row is not None and cache_is_fresh(row.checked_at, ttl):
            explanation = (
                row.payload.get("explanation")
                if isinstance(row.payload, dict)
                else None
            )
            if isinstance(explanation, str) and explanation:
                observe_ai_cache("cve_explain", hit=True)
                response.headers["X-AI-Cache"] = "hit"
                return CveExplanation(
                    explanation=explanation,
                    cached=True,
                    model=row.model,
                    generated_at=utcnow(),
                )

        observe_ai_cache("cve_explain", hit=False)
        explanation = await service.explain_cve(payload.cve_id, payload.summary)
        observe_llm_call(
            "cve_explain",
            config.provider,
            "ok" if explanation is not None else "error",
        )
        if explanation is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM недоступна. Проверьте настройки.",
            )

        if row is None:
            row = AICache(
                key=cache_key,
                kind="cve_explain",
                model=config.model,
            )
            session.add(row)
        row.payload = {"explanation": explanation}
        row.checked_at = utcnow()
        await session.commit()

    response.headers["X-AI-Cache"] = "miss"
    return CveExplanation(
        explanation=explanation,
        cached=False,
        model=config.model,
        generated_at=utcnow(),
    )


@router.post(
    "/repositories/{repository_id}/ai/agent-task",
    response_model=AgentTask,
)
async def generate_repository_agent_task(
    repository_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: AgentTaskRequest | None = None,
) -> AgentTask:
    repository = await _get_repository(session, repository_id)
    status = await _status_service(request).get_status(
        session,
        repository,
        use_cache=True,
        fetch=False,
    )
    status_response = RepositoryStatusResponse.model_validate(status)
    service: AgentTaskService = request.app.state.agent_task_service
    try:
        return await service.generate(
            repository,
            status_response,
            language=payload.language if payload else "ru",
        )
    except AgentTaskUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    "/repositories/{repository_id}/actions/update-dependencies",
    response_model=ActionLogResponse,
)
async def update_repository_dependencies(
    repository_id: int,
    payload: DependencyUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionLogResponse:
    repository = await _get_repository(session, repository_id)
    try:
        entry = await _dependency_update_service(request).update(
            session,
            repository,
            payload.ecosystem,
            confirm=payload.confirm,
        )
    except DependencyUpdateError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.message
        ) from exc
    if entry.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=entry.error or "dependency update failed",
        )
    return ActionLogResponse.model_validate(entry)


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


@router.post(
    "/repositories/actions/update_dependencies_all",
    status_code=status.HTTP_202_ACCEPTED,
)
async def bulk_update_dependencies(
    payload: BulkDependencyUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirmation_required",
        )
    background_tasks.add_task(
        _dependency_update_service(request).update_many,
        payload.repo_ids,
        payload.ecosystem,
        actor="bulk",
    )
    return {
        "status": "accepted",
        "action": "update_dependencies_all",
        "ecosystem": payload.ecosystem,
        "repo_ids": payload.repo_ids,
    }


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


@router.get(
    "/repositories/{repository_id}/tags",
    response_model=RepositoryTagsResponse,
)
async def repository_tags(
    repository_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryTagsResponse:
    repository = await _get_repository(session, repository_id)
    tags = await asyncio.to_thread(list_tags, repository.path)
    return RepositoryTagsResponse(repository_id=repository_id, tags=tags)


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
