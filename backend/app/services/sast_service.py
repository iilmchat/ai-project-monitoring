"""Read-only SAST orchestration (v1.3.0, Sprint 59).

Tools are external optional binaries. Missing tools produce
``status="unavailable"`` instead of a 500; analysis never executes project code.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.subprocess_flags import WINDOWS_CREATION_FLAGS
from app.db.base import utcnow
from app.models.entities import SastCache
from app.schemas.sast import (
    SastFinding,
    SastReport,
    SastSeverity,
    SastSummary,
    SastToolReport,
)
from app.services.secret_scanner import redact_secrets

logger = structlog.get_logger(__name__)

SAST_TOOLS = ("bandit", "semgrep", "eslint")
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
_BANDIT_SEVERITY = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_SEMGREP_SEVERITY = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
_MAX_SNIPPET_CHARS = 300
_EXCLUDED_DIRS = "bin,obj,node_modules,.venv,venv,vendor,dist,build,target,.git"

MinSeverity = Literal["critical", "high", "medium", "low", "all"]
SastTools = Literal["all", "bandit", "semgrep", "eslint"]


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    missing: bool = False
    error: str | None = None


class ToolRunner(Protocol):
    """Callable used to run one external SAST tool."""

    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> ToolResult:
        """Run ``args`` and return a normalized result."""


async def run_tool(
    args: Sequence[str], cwd: str, timeout: float
) -> ToolResult:
    """Run one external SAST tool without a shell."""
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
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
        return ToolResult(ok=False, exit_code=-1, missing=True, error=str(exc))

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return ToolResult(
            ok=False,
            exit_code=-1,
            timed_out=True,
            error="timeout",
        )

    return ToolResult(
        ok=process.returncode == 0,
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


class SastService:
    """Run bandit/semgrep/eslint and cache normalized findings."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        enabled: bool = True,
        cache_ttl_seconds: int = 86400,
        timeout_seconds: float = 120.0,
        max_findings: int = 500,
        max_output_bytes: int = 8 * 1024 * 1024,
        semgrep_config: str = "",
        tool_commands: dict[str, list[str] | None] | None = None,
        runner: ToolRunner = run_tool,
    ) -> None:
        self._session_factory = session_factory
        self._enabled = enabled
        self._ttl = max(cache_ttl_seconds, 0)
        self._timeout = max(timeout_seconds, 1.0)
        self._max_findings = max(max_findings, 1)
        self._max_output_bytes = max(max_output_bytes, 1024)
        self._semgrep_config = semgrep_config.strip()
        self._tool_commands = tool_commands
        self._runner = runner
        self._rules_path = (
            Path(__file__).resolve().parent.parent / "sast_rules" / "default.yml"
        )

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        refresh: bool = False,
        tools: SastTools = "all",
        min_severity: MinSeverity = "all",
    ) -> SastReport:
        """Return a cached or freshly computed SAST report."""
        if not self._enabled:
            return _empty_report(
                repository_id,
                status="unavailable",
                error="sast_disabled",
                tool_names=_requested_tools(tools),
            )

        key = await self._cache_key(repository_id, repo_path, tools)
        if not refresh:
            cached = await self._read_cache(key)
            if cached is not None:
                return cached.model_copy(
                    update={"cached": True, "checked_at": utcnow()}
                )

        report = await self._scan(
            repository_id,
            repo_path,
            tools=tools,
            min_severity=min_severity,
        )
        if report.status != "unavailable":
            await self._write_cache(key, repository_id, report)
        return report

    async def _scan(
        self,
        repository_id: int,
        repo_path: str,
        *,
        tools: SastTools,
        min_severity: MinSeverity,
    ) -> SastReport:
        root = Path(repo_path).resolve()
        commands = self._commands(root)
        requested = _requested_tools(tools)
        tool_reports: list[SastToolReport] = []
        findings: list[SastFinding] = []
        truncated = False
        first_error: str | None = None

        for name in requested:
            command = commands.get(name)
            if not command:
                tool_reports.append(
                    SastToolReport(
                        name=name,
                        status="unavailable",
                        error="not_installed",
                    )
                )
                continue
            started = time.perf_counter()
            args = self._args(name, command, root)
            if args is None:
                tool_reports.append(
                    SastToolReport(
                        name=name,
                        status="unavailable",
                        error="rules_not_found",
                    )
                )
                continue
            result = await self._runner(args, str(root), self._timeout)
            duration_ms = int((time.perf_counter() - started) * 1000)
            if result.missing:
                tool_reports.append(
                    SastToolReport(
                        name=name,
                        status="unavailable",
                        duration_ms=duration_ms,
                        error="not_installed",
                    )
                )
                continue
            if result.timed_out:
                tool_reports.append(
                    SastToolReport(
                        name=name,
                        status="error",
                        duration_ms=duration_ms,
                        error="timeout",
                    )
                )
                first_error = first_error or "timeout"
                continue
            if len(result.stdout) > self._max_output_bytes:
                truncated = True
            parsed, error = _parse_tool_output(name, result.stdout, root)
            if error is not None:
                tool_reports.append(
                    SastToolReport(
                        name=name,
                        status="error",
                        duration_ms=duration_ms,
                        error=error,
                    )
                )
                first_error = first_error or error
                continue
            tool_reports.append(
                SastToolReport(
                    name=name,
                    status="ok",
                    duration_ms=duration_ms,
                )
            )
            findings.extend(parsed)

        unique = _deduplicate(findings)
        summary = _summary(unique)
        visible = unique
        if min_severity != "all":
            threshold = _SEVERITY_RANK[min_severity]
            visible = [
                item
                for item in unique
                if _SEVERITY_RANK[item.severity] <= threshold
            ]
        if len(visible) > self._max_findings:
            visible = visible[: self._max_findings]
            truncated = True

        ok_tools = [item for item in tool_reports if item.status == "ok"]
        if not ok_tools:
            status: Literal["ok", "partial", "unavailable"] = "unavailable"
        elif len(ok_tools) < len(tool_reports) or truncated:
            status = "partial"
        else:
            status = "ok"

        return SastReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            status=status,
            tools=tool_reports,
            summary=summary,
            findings=visible,
            truncated=truncated,
            error=first_error,
            cached=False,
        )

    def _commands(self, root: Path) -> dict[str, list[str] | None]:
        if self._tool_commands is not None:
            return dict(self._tool_commands)

        commands: dict[str, list[str] | None] = {
            "bandit": _detect_bandit(),
            "semgrep": _detect_semgrep(),
            "eslint": None,
        }
        if commands["semgrep"] is None:
            commands["eslint"] = _detect_eslint(root)
        return commands

    def _args(
        self, name: str, command: list[str], root: Path
    ) -> list[str] | None:
        if name == "bandit":
            return [
                *command,
                "-r",
                str(root),
                "-f",
                "json",
                "-q",
                "-x",
                _EXCLUDED_DIRS,
            ]
        if name == "semgrep":
            config = self._semgrep_config or str(self._rules_path)
            if not Path(config).is_file():
                return None
            excludes: list[str] = []
            for directory in _EXCLUDED_DIRS.split(","):
                excludes.extend(["--exclude", directory])
            return [
                *command,
                "--json",
                "--config",
                config,
                "--metrics=off",
                "--disable-version-check",
                *excludes,
                str(root),
            ]
        return [
            *command,
            ".",
            "--format",
            "json",
            "--no-error-on-unmatched-pattern",
        ]

    async def _cache_key(
        self, repository_id: int, repo_path: str, tools: SastTools
    ) -> str:
        head, dirty = await self._snapshot(repo_path)
        return f"sast:{repository_id}:{head}:{dirty}:{tools}"

    async def _snapshot(self, repo_path: str) -> tuple[str, str]:
        cwd = str(Path(repo_path))
        head_result = await self._runner(
            ["git", "-C", cwd, "rev-parse", "HEAD"], cwd, 5
        )
        dirty_result = await self._runner(
            ["git", "-C", cwd, "status", "--porcelain"], cwd, 5
        )
        head = head_result.stdout.strip() if head_result.ok else "no-head"
        dirty_raw = dirty_result.stdout if dirty_result.ok else ""
        dirty = hashlib.sha256(dirty_raw.encode("utf-8")).hexdigest()[:16]
        return head[:40] or "no-head", dirty

    async def _read_cache(self, key: str) -> SastReport | None:
        if self._ttl <= 0:
            return None
        async with self._session_factory() as session:
            row = await session.get(SastCache, key)
            if row is None:
                return None
            checked_at = row.checked_at
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=UTC)
            age = (utcnow() - checked_at).total_seconds()
            if not 0 <= age < self._ttl:
                return None
            try:
                return SastReport.model_validate(row.payload)
            except ValueError:
                return None

    async def _write_cache(
        self, key: str, repository_id: int, report: SastReport
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(SastCache, key)
            if row is None:
                row = SastCache(key=key, repository_id=repository_id)
                session.add(row)
            row.payload = report.model_dump(mode="json")
            row.checked_at = utcnow()
            await session.commit()


def _detect_bandit() -> list[str] | None:
    binary = shutil.which("bandit")
    if binary:
        return [binary]
    if importlib.util.find_spec("bandit") is not None:
        return [sys.executable, "-m", "bandit"]
    return None


def _detect_semgrep() -> list[str] | None:
    binary = shutil.which("semgrep")
    return [binary] if binary else None


def _detect_eslint(root: Path) -> list[str] | None:
    for name in ("eslint", "eslint.cmd"):
        candidate = root / "node_modules" / ".bin" / name
        if candidate.is_file():
            return [str(candidate)]
    return None


def _requested_tools(tools: SastTools) -> tuple[str, ...]:
    return SAST_TOOLS if tools == "all" else (tools,)


def _parse_tool_output(
    tool: str, output: str, root: Path
) -> tuple[list[SastFinding], str | None]:
    try:
        payload = json.loads(output) if output.strip() else None
    except ValueError:
        return [], "invalid_output"
    if payload is None:
        return [], "empty_output"
    if tool == "bandit":
        return _parse_bandit(payload, root)
    if tool == "semgrep":
        return _parse_semgrep(payload, root)
    return _parse_eslint(payload, root)


def _parse_bandit(
    payload: object, root: Path
) -> tuple[list[SastFinding], str | None]:
    if not isinstance(payload, dict):
        return [], "invalid_output"
    results = payload.get("results")
    if not isinstance(results, list):
        return [], "invalid_output"
    findings: list[SastFinding] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        file = _relative_file(root, item.get("filename"))
        line = _as_int(item.get("line_number"))
        if file is None or line is None:
            continue
        rule_id = str(item.get("test_id") or item.get("test_name") or "bandit")
        message = str(item.get("issue_text") or item.get("test_name") or rule_id)
        severity = _BANDIT_SEVERITY.get(
            str(item.get("issue_severity") or "").upper(), "unknown"
        )
        cwe_raw = item.get("issue_cwe")
        cwe = (
            f"CWE-{cwe_raw.get('id')}"
            if isinstance(cwe_raw, dict) and cwe_raw.get("id") is not None
            else None
        )
        findings.append(
            _finding(
                tool="bandit",
                rule_id=rule_id,
                severity=severity,  # type: ignore[arg-type]
                confidence=_lower(item.get("issue_confidence")),
                category="security",
                cwe=cwe,
                file=file,
                line=line,
                column=None,
                message=message,
                snippet=item.get("code"),
            )
        )
    return findings, None


def _parse_semgrep(
    payload: object, root: Path
) -> tuple[list[SastFinding], str | None]:
    if not isinstance(payload, dict):
        return [], "invalid_output"
    results = payload.get("results")
    if not isinstance(results, list):
        return [], "invalid_output"
    findings: list[SastFinding] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        file = _relative_file(root, item.get("path"))
        start = item.get("start")
        line = _as_int(start.get("line")) if isinstance(start, dict) else None
        if file is None or line is None:
            continue
        extra = item.get("extra")
        message = (
            str(extra.get("message") or item.get("check_id") or "semgrep")
            if isinstance(extra, dict)
            else "semgrep"
        )
        severity_raw = (
            str(extra.get("severity") or "").upper()
            if isinstance(extra, dict)
            else ""
        )
        metadata = extra.get("metadata") if isinstance(extra, dict) else None
        cwe = _metadata_cwe(metadata)
        findings.append(
            _finding(
                tool="semgrep",
                rule_id=str(item.get("check_id") or "semgrep"),
                severity=_SEMGREP_SEVERITY.get(severity_raw, "unknown"),  # type: ignore[arg-type]
                confidence=None,
                category="security",
                cwe=cwe,
                file=file,
                line=line,
                column=_as_int(start.get("col")) if isinstance(start, dict) else None,
                message=message,
                snippet=extra.get("lines") if isinstance(extra, dict) else None,
            )
        )
    return findings, None


def _parse_eslint(
    payload: object, root: Path
) -> tuple[list[SastFinding], str | None]:
    if not isinstance(payload, list):
        return [], "invalid_output"
    findings: list[SastFinding] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        file = _relative_file(root, entry.get("filePath"))
        if file is None:
            continue
        messages = entry.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            line = _as_int(message.get("line"))
            if line is None:
                continue
            severity_raw = _as_int(message.get("severity"))
            severity: SastSeverity = "high" if severity_raw == 2 else "medium"
            findings.append(
                _finding(
                    tool="eslint",
                    rule_id=str(message.get("ruleId") or "eslint"),
                    severity=severity,
                    confidence=None,
                    category="lint",
                    cwe=None,
                    file=file,
                    line=line,
                    column=_as_int(message.get("column")),
                    message=str(message.get("message") or "lint issue"),
                    snippet=None,
                )
            )
    return findings, None


def _finding(
    *,
    tool: str,
    rule_id: str,
    severity: SastSeverity,
    confidence: str | None,
    category: str | None,
    cwe: str | None,
    file: str,
    line: int,
    column: int | None,
    message: str,
    snippet: object,
) -> SastFinding:
    snippet_text = redact_secrets(str(snippet))[:_MAX_SNIPPET_CHARS] if snippet else None
    fingerprint = hashlib.sha256(
        f"{file}:{line}:{rule_id}:{message.lower()}".encode()
    ).hexdigest()
    return SastFinding(
        tool=tool,
        rule_id=rule_id,
        severity=severity,
        confidence=confidence,
        category=category,
        cwe=cwe,
        file=file,
        line=line,
        column=column,
        message=message,
        snippet=snippet_text,
        fingerprint=fingerprint,
    )


def _deduplicate(findings: list[SastFinding]) -> list[SastFinding]:
    unique: dict[str, SastFinding] = {}
    for item in findings:
        key = item.fingerprint
        existing = unique.get(key)
        if existing is None:
            unique[key] = item
            continue
        if existing.tool != item.tool:
            tools = sorted({existing.tool, item.tool})
            unique[key] = existing.model_copy(
                update={"tool": ", ".join(tools)}
            )
    return sorted(
        unique.values(),
        key=lambda item: (
            _SEVERITY_RANK[item.severity],
            item.file,
            item.line,
            item.rule_id,
        ),
    )


def _summary(findings: list[SastFinding]) -> SastSummary:
    counts: dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 0,
    }
    for item in findings:
        counts[item.severity] += 1
    return SastSummary(total=len(findings), **counts)


def _empty_report(
    repository_id: int,
    *,
    status: Literal["ok", "partial", "unavailable"],
    error: str | None,
    tool_names: Sequence[str],
) -> SastReport:
    return SastReport(
        repository_id=repository_id,
        checked_at=utcnow(),
        status=status,
        tools=[
            SastToolReport(name=name, status="unavailable", error=error)
            for name in tool_names
        ],
        error=error,
        cached=False,
    )


def _relative_file(root: Path, raw: object) -> str | None:
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved.relative_to(root).as_posix()


def _metadata_cwe(metadata: object) -> str | None:
    if not isinstance(metadata, dict):
        return None
    cwe = metadata.get("cwe")
    if isinstance(cwe, list) and cwe:
        return str(cwe[0])
    if isinstance(cwe, str) and cwe:
        return cwe
    return None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _lower(value: object) -> str | None:
    return str(value).lower() if isinstance(value, str) and value else None


__all__ = ["SAST_TOOLS", "SastService", "ToolResult", "ToolRunner", "run_tool"]
