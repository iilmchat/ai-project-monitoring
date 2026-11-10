"""Explicit, preflight-checked dependency updates (S34-001, S57-003)."""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.subprocess_flags import WINDOWS_CREATION_FLAGS
from app.db.base import utcnow
from app.models.entities import ActionLog, Repository

logger = structlog.get_logger(__name__)

Ecosystem = Literal["python", "node", "dotnet"]
MAX_OUTPUT_CHARS = 10000
DEFAULT_TIMEOUT_SECONDS = 180
_BULK_CONCURRENCY = 2
_MAX_DOTNET_PROJECTS = 20
_DOTNET_PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
_DOTNET_IGNORED_DIRS = frozenset(
    {"bin", "obj", ".vs", ".git", "node_modules", ".venv", "packages"}
)
_URL_CREDENTIALS = re.compile(r"(https?://)[^/\s@]+@")


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of one update command."""

    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None


class CommandRunner(Protocol):
    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> CommandResult:
        """Run ``args`` in ``cwd`` and return a normalized result."""


async def run_command(
    args: Sequence[str], cwd: str, timeout: float
) -> CommandResult:
    """Run a package-manager command without shell interpolation."""
    environment = dict(os.environ)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            creationflags=WINDOWS_CREATION_FLAGS,
        )
    except OSError as exc:
        return CommandResult(ok=False, exit_code=-1, error=str(exc))

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return CommandResult(
            ok=False,
            exit_code=-1,
            timed_out=True,
            error="timeout",
        )

    return CommandResult(
        ok=process.returncode == 0,
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        error=None if process.returncode == 0 else "command_failed",
    )


class DependencyUpdateError(Exception):
    """A preflight/execution error that maps to a domain HTTP response."""

    def __init__(self, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DependencyUpdateService:
    """Update pip/pnpm/npm dependencies on a clean worktree, with audit."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_output_chars: int = MAX_OUTPUT_CHARS,
        runner: CommandRunner = run_command,
    ) -> None:
        self._session_factory = session_factory
        self._timeout = max(timeout_seconds, 1)
        self._max_output_chars = max(max_output_chars, 1000)
        self._runner = runner

    async def update(
        self,
        session: AsyncSession,
        repository: Repository,
        ecosystem: Ecosystem,
        *,
        confirm: bool,
        actor: str = "local",
    ) -> ActionLog:
        """Run the update for one repository after the safety preflight."""
        if not confirm:
            raise DependencyUpdateError(
                "confirmation_required", status_code=400
            )
        if ecosystem not in {"python", "node", "dotnet"}:
            raise DependencyUpdateError("unsupported ecosystem", status_code=400)

        dotnet_projects: list[str] | None = None
        try:
            if ecosystem == "dotnet":
                dotnet_projects = self._dotnet_projects(repository.path)
                command = "dotnet add package --no-restore"
                args: list[str] = []
            else:
                command, args = self._command(repository.path, ecosystem)
        except DependencyUpdateError as exc:
            await self._log(
                session,
                repository,
                f"{ecosystem} update",
                status="error",
                error=exc.message,
                actor=actor,
            )
            raise

        started = time.perf_counter()

        status = await self._runner(
            ["git", "status", "--porcelain"],
            str(Path(repository.path)),
            5,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        if not status.ok:
            await self._log(
                session,
                repository,
                command,
                status="error",
                error="git_unavailable",
                duration_ms=duration_ms,
                actor=actor,
            )
            raise DependencyUpdateError("git_unavailable")
        if status.stdout.strip():
            await self._log(
                session,
                repository,
                command,
                status="error",
                error="dirty_worktree",
                duration_ms=duration_ms,
                actor=actor,
            )
            raise DependencyUpdateError("Worktree must be clean")

        result = (
            await self._run_dotnet(dotnet_projects or [], str(Path(repository.path)))
            if ecosystem == "dotnet"
            else await self._runner(
                args, str(Path(repository.path)), self._timeout
            )
        )
        if (
            ecosystem == "dotnet"
            and not result.ok
            and (result.error == "dotnet_unavailable" or _is_missing_executable(result))
        ):
            duration_ms = int((time.perf_counter() - started) * 1000)
            await self._log(
                session,
                repository,
                command,
                status="error",
                error="dotnet_unavailable",
                duration_ms=duration_ms,
                actor=actor,
            )
            raise DependencyUpdateError("dotnet_unavailable")
        duration_ms = int((time.perf_counter() - started) * 1000)
        output = _format_output(result, self._max_output_chars)
        entry = await self._log(
            session,
            repository,
            command,
            status="success" if result.ok else "error",
            output=output,
            error=result.error,
            exit_code=result.exit_code,
            duration_ms=duration_ms,
            actor=actor,
        )
        logger.info(
            "dependency_update_finished",
            repository_id=repository.id,
            ecosystem=ecosystem,
            status=entry.status,
            duration_ms=duration_ms,
            timed_out=result.timed_out,
        )
        return entry

    async def update_many(
        self,
        repository_ids: list[int] | None,
        ecosystem: Ecosystem,
        *,
        actor: str = "bulk",
    ) -> list[ActionLog]:
        """Update many repositories with limited concurrency."""
        ids = repository_ids
        if ids is None:
            async with self._session_factory() as session:
                result = await session.scalars(
                    select(Repository.id).where(Repository.tracked.is_(True))
                )
                ids = list(result.all())

        semaphore = asyncio.Semaphore(_BULK_CONCURRENCY)

        async def one(repository_id: int) -> ActionLog | None:
            async with semaphore, self._session_factory() as session:
                repository = await session.get(Repository, repository_id)
                if repository is None:
                    return None
                try:
                    return await self.update(
                        session,
                        repository,
                        ecosystem,
                        confirm=True,
                        actor=actor,
                    )
                except DependencyUpdateError:
                    return None

        results = await asyncio.gather(*(one(repository_id) for repository_id in ids))
        return [entry for entry in results if entry is not None]

    def _dotnet_projects(self, repo_path: str) -> list[str]:
        root = Path(repo_path)
        projects: list[str] = []
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            current, level = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file() and entry.suffix.lower() in _DOTNET_PROJECT_SUFFIXES:
                        projects.append(entry.relative_to(root).as_posix())
                except OSError:
                    continue
            if level >= 3:
                continue
            for entry in entries:
                try:
                    if not entry.is_dir() or entry.is_symlink():
                        continue
                except OSError:
                    continue
                if entry.name.lower() in _DOTNET_IGNORED_DIRS or entry.name.startswith("."):
                    continue
                stack.append((entry, level + 1))
        projects.sort()
        if not projects:
            raise DependencyUpdateError("no_manifest")
        return projects[:_MAX_DOTNET_PROJECTS]

    async def _run_dotnet(
        self, projects: Sequence[str], cwd: str
    ) -> CommandResult:
        """Run ``dotnet list --outdated`` then ``dotnet add`` for each package."""
        outputs: list[str] = []
        errors: list[str] = []
        ok = True
        timed_out = False
        exit_code = 0

        for project in projects:
            listed = await self._runner(
                [
                    "dotnet",
                    "list",
                    project,
                    "package",
                    "--outdated",
                    "--no-restore",
                ],
                cwd,
                self._timeout,
            )
            outputs.extend(part for part in (listed.stdout, listed.stderr) if part.strip())
            timed_out = timed_out or listed.timed_out
            if not listed.ok:
                ok = False
                exit_code = listed.exit_code or -1
                if _is_missing_executable(listed):
                    return CommandResult(
                        ok=False,
                        exit_code=-1,
                        stdout="\n".join(outputs),
                        stderr="\n".join(errors),
                        error="dotnet_unavailable",
                    )
                errors.append(listed.error or "dotnet_list_failed")
                continue

            for package in _parse_outdated_packages(listed.stdout):
                added = await self._runner(
                    [
                        "dotnet",
                        "add",
                        project,
                        "package",
                        package,
                        "--no-restore",
                    ],
                    cwd,
                    self._timeout,
                )
                outputs.extend(
                    part for part in (added.stdout, added.stderr) if part.strip()
                )
                timed_out = timed_out or added.timed_out
                if not added.ok:
                    ok = False
                    exit_code = added.exit_code or -1
                    if _is_missing_executable(added):
                        return CommandResult(
                            ok=False,
                            exit_code=-1,
                            stdout="\n".join(outputs),
                            stderr="\n".join(errors),
                            error="dotnet_unavailable",
                        )
                    errors.append(added.error or "dotnet_add_failed")

        return CommandResult(
            ok=ok,
            exit_code=0 if ok else exit_code,
            stdout="\n".join(outputs),
            stderr="\n".join(errors),
            timed_out=timed_out,
            error=None if ok else (errors[0] if errors else "command_failed"),
        )

    def _command(self, repo_path: str, ecosystem: Ecosystem) -> tuple[str, list[str]]:
        root = Path(repo_path)
        if ecosystem == "python":
            if not (root / "requirements.txt").is_file():
                raise DependencyUpdateError("no_manifest")
            return (
                "pip install -r requirements.txt --upgrade",
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                    "--upgrade",
                ],
            )
        if ecosystem == "dotnet":
            raise DependencyUpdateError("unsupported ecosystem", status_code=400)
        if not (root / "package.json").is_file():
            raise DependencyUpdateError("no_manifest")
        if (root / "pnpm-lock.yaml").is_file():
            return "pnpm update", ["pnpm", "update"]
        return "npm update", ["npm", "update"]

    async def _log(
        self,
        session: AsyncSession,
        repository: Repository,
        command: str,
        *,
        status: str,
        output: str | None = None,
        error: str | None = None,
        exit_code: int | None = None,
        duration_ms: int = 0,
        actor: str = "local",
    ) -> ActionLog:
        entry = ActionLog(
            repository_id=repository.id,
            action="update-dependencies",
            command=command,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            exit_code=exit_code,
            actor=actor,
            created_at=utcnow(),
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry


def _format_output(result: CommandResult, max_chars: int) -> str | None:
    parts = [part for part in (result.stdout, result.stderr) if part.strip()]
    if not parts:
        return None
    return _redact("\n".join(parts), max_chars)


def _parse_outdated_packages(output: str) -> list[str]:
    """Extract package ids from ``dotnet list package --outdated`` output."""
    packages: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(">"):
            continue
        parts = stripped[1:].split()
        if not parts:
            continue
        name = parts[0]
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        packages.append(name)
    return packages


def _is_missing_executable(result: CommandResult) -> bool:
    if result.exit_code != -1:
        return False
    message = (result.error or result.stderr or "").lower()
    return any(
        marker in message
        for marker in (
            "no such file",
            "not found",
            "winerror 2",
            "cannot find",
        )
    )


def _redact(value: str, max_chars: int) -> str:
    redacted = _URL_CREDENTIALS.sub(r"\1****@", value)
    if len(redacted) > max_chars:
        return redacted[:max_chars] + "\n… (truncated)"
    return redacted


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_OUTPUT_CHARS",
    "CommandResult",
    "CommandRunner",
    "DependencyUpdateError",
    "DependencyUpdateService",
    "run_command",
]
