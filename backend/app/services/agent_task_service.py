"""Generate Markdown tasks for DSH/OpenCode agents (S38-002)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from app.db.base import utcnow
from app.git.command_backend import get_conflicts
from app.git.pygit2_backend import GitStatusError, read_commits
from app.models.entities import Repository
from app.schemas.ai import AgentTask
from app.schemas.repository import RepositoryStatusResponse
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class AgentTaskUnavailableError(Exception):
    """LLM is disabled/remote-blocked or returned no task."""


class AgentTaskService:
    """Build a grounded context and ask the LLM to write an agent task."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def generate(
        self,
        repository: Repository,
        status: RepositoryStatusResponse,
        *,
        language: str = "ru",
    ) -> AgentTask:
        if not self._llm.enabled or not self._llm.remote_allowed():
            raise AgentTaskUnavailableError("llm_unavailable")

        conflicts = await asyncio.to_thread(get_conflicts, repository.path)
        try:
            commits = await asyncio.to_thread(read_commits, repository.path, "HEAD", 8)
        except GitStatusError:
            commits = []

        context = {
            "repository": repository.alias or Path(repository.path).name,
            "path": repository.path,
            "state": status.state,
            "branch": status.branch or "—",
            "upstream": status.upstream or "—",
            "ahead": status.ahead,
            "behind": status.behind,
            "dirty": (
                f"{status.dirty.modified}/{status.dirty.staged}/"
                f"{status.dirty.untracked}"
            ),
            "conflicts": conflicts,
            "commits": [commit.subject for commit in commits],
        }
        task = await self._llm.generate_agent_task(context, language=language)
        if task is None:
            raise AgentTaskUnavailableError("llm_unavailable")

        logger.info(
            "agent_task_generated",
            repository_id=repository.id,
            state=status.state,
            conflicts=len(conflicts),
            commits=len(commits),
        )
        return AgentTask(
            task=task,
            model=self._llm.model,
            generated_at=utcnow(),
        )


__all__ = ["AgentTaskService", "AgentTaskUnavailableError"]
