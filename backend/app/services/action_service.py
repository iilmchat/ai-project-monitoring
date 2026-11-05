"""Explicit, confirmed mutations with audit trail (ADR-0003, Sprint 10).

Only a fixed whitelist of actions is executable, and only after the caller
passes ``confirm=true``. Destructive commands are intentionally absent.
"""

from __future__ import annotations

import asyncio
import time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.git.command_backend import run_git
from app.models.entities import ActionLog, Repository, RepositoryStatus

logger = structlog.get_logger(__name__)

MUTATION_ACTIONS = frozenset({"fetch", "pull", "push", "push_mirror", "stash"})
MAX_OUTPUT_CHARS = 4000


class ActionError(Exception):
    """Base class for action execution errors."""


class ConfirmationRequiredError(ActionError):
    """Mutation was requested without ``confirm=true``."""


class UnknownActionError(ActionError):
    """Requested action is not in the executable whitelist."""


class ActionNotAllowedError(ActionError):
    """Action cannot be executed for the current repository state."""


class ActionService:
    """Execute whitelisted Git mutations and persist an audit record."""

    def __init__(self, timeout_seconds: int = 60) -> None:
        self._timeout = timeout_seconds

    async def execute_action(
        self,
        session: AsyncSession,
        repository: Repository,
        action: str,
        *,
        confirm: bool,
    ) -> ActionLog:
        if not confirm:
            raise ConfirmationRequiredError("Action requires confirmation")

        normalized = action.strip().lower().replace("-", "_")
        if normalized == "push_mirror":
            return await self.push_mirror(session, repository, confirm=confirm)
        if normalized not in MUTATION_ACTIONS:
            raise UnknownActionError(
                f"unknown action {action!r}; allowed: {sorted(MUTATION_ACTIONS)}"
            )

        if normalized == "fetch":
            args = ["fetch", "--all", "--prune"]
        elif normalized == "pull":
            args = ["pull"]
        elif normalized == "push":
            branch = await self._current_branch(session, repository.id)
            args = ["push", "origin", branch]
        else:
            args = ["stash", "save", "Auto-stash from IIRuchating"]

        return await self._run_and_log(session, repository, normalized, args)

    async def push_mirror(
        self,
        session: AsyncSession,
        repository: Repository,
        *,
        confirm: bool,
    ) -> ActionLog:
        if not confirm:
            raise ConfirmationRequiredError("Action requires confirmation")
        if not repository.gitflic_full_name:
            raise ActionNotAllowedError(
                "gitflic_full_name is not configured for this repository"
            )
        branch = await self._current_branch(session, repository.id)
        return await self._run_and_log(
            session,
            repository,
            "push_mirror",
            ["push", "gitflic", branch],
        )

    async def _run_and_log(
        self,
        session: AsyncSession,
        repository: Repository,
        action: str,
        args: list[str],
    ) -> ActionLog:
        command = "git " + " ".join(args)
        started = time.perf_counter()
        result = await asyncio.to_thread(
            run_git,
            args,
            cwd=repository.path,
            timeout=self._timeout,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)

        output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n… (truncated)"

        entry = ActionLog(
            repository_id=repository.id,
            action=action,
            command=command,
            status="success" if result.ok else "error",
            output=output or None,
            error=result.error,
            duration_ms=duration_ms,
            exit_code=result.exit_code,
            actor="local",
            created_at=utcnow(),
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

        logger.info(
            "action_executed",
            repository_id=repository.id,
            action=action,
            status=entry.status,
            exit_code=result.exit_code,
            duration_ms=duration_ms,
            timed_out=result.timed_out,
        )
        return entry

    async def _current_branch(self, session: AsyncSession, repository_id: int) -> str:
        row = await session.scalar(
            select(RepositoryStatus).where(RepositoryStatus.repository_id == repository_id)
        )
        return row.branch if row is not None and row.branch else "main"


__all__ = [
    "MUTATION_ACTIONS",
    "ActionError",
    "ActionNotAllowedError",
    "ActionService",
    "ConfirmationRequiredError",
    "UnknownActionError",
]
