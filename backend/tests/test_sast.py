"""SAST service and API tests (v1.3.0, Sprint 59)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from app.models.entities import Repository
from app.services import sast_service as sast_module
from app.services.sast_service import SastService, ToolResult
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeRunner:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.bandit_calls = 0
        self.calls: list[list[str]] = []

    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> ToolResult:
        self.calls.append(list(args))
        if args and args[0] == "git":
            if "rev-parse" in args:
                return ToolResult(ok=True, exit_code=0, stdout="abc123\n")
            return ToolResult(ok=True, exit_code=0, stdout="")
        if "bandit" in args[0] or args[0].endswith("bandit"):
            self.bandit_calls += 1
            return ToolResult(
                ok=False,
                exit_code=1,
                stdout=json.dumps(self.payload),
            )
        return ToolResult(ok=False, exit_code=1, stdout="{}")


def _bandit_payload() -> dict[str, object]:
    return {
        "results": [
            {
                "filename": "app/utils.py",
                "line_number": 42,
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
                "issue_text": "subprocess call with shell=True",
                "code": "subprocess.run(cmd, shell=True)",
                "issue_cwe": {"id": 78},
            },
            {
                "filename": "app/db.py",
                "line_number": 10,
                "issue_severity": "MEDIUM",
                "issue_confidence": "MEDIUM",
                "test_id": "B608",
                "test_name": "hardcoded_sql_expressions",
                "issue_text": "Possible SQL injection",
                "code": "query = f'SELECT * FROM {table}'",
            },
        ]
    }


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "app").mkdir()
    (path / "app" / "utils.py").write_text("x = 1\n", encoding="utf-8")
    return path


async def test_sast_report_parses_bandit_and_caches(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "repo")
    runner = FakeRunner(_bandit_payload())
    service = SastService(
        session_factory,
        tool_commands={
            "bandit": ["bandit"],
            "semgrep": None,
            "eslint": None,
        },
        runner=runner,
    )

    report = await service.get_report(1, str(repo))
    assert report.status == "partial"
    assert report.summary.high == 1
    assert report.summary.medium == 1
    assert report.findings[0].file == "app/utils.py"
    assert report.findings[0].cwe == "CWE-78"
    assert report.findings[0].line == 42
    assert runner.bandit_calls == 1

    cached = await service.get_report(1, str(repo))
    assert cached.cached is True
    assert runner.bandit_calls == 1

    refreshed = await service.get_report(1, str(repo), refresh=True)
    assert refreshed.cached is False
    assert runner.bandit_calls == 2


async def test_sast_missing_tools_are_unavailable(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "empty")
    service = SastService(
        session_factory,
        tool_commands={
            "bandit": None,
            "semgrep": None,
            "eslint": None,
        },
        runner=FakeRunner({}),
    )

    report = await service.get_report(1, str(repo))

    assert report.status == "unavailable"
    assert report.findings == []
    assert {item.status for item in report.tools} == {"unavailable"}


async def test_sast_timeout_is_partial(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "timeout")

    class TimeoutRunner(FakeRunner):
        async def __call__(
            self, args: Sequence[str], cwd: str, timeout: float
        ) -> ToolResult:
            if args and args[0] == "git":
                return await super().__call__(args, cwd, timeout)
            return ToolResult(ok=False, exit_code=-1, timed_out=True, error="timeout")

    service = SastService(
        session_factory,
        tool_commands={"bandit": ["bandit"]},
        runner=TimeoutRunner({}),
    )

    report = await service.get_report(1, str(repo), tools="bandit")

    assert report.status == "unavailable"
    assert report.tools[0].status == "error"
    assert report.error == "timeout"


def test_bandit_detection_uses_module_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr(sast_module.shutil, "which", lambda _: None)
    monkeypatch.setattr(sast_module.importlib.util, "find_spec", lambda _: object())

    assert sast_module._detect_bandit() == [
        sast_module.sys.executable,
        "-m",
        "bandit",
    ]


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_sast_api(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "api")
    repository_id = await _create_repository(session_factory, repo)
    app.state.sast_service = SastService(
        session_factory,
        tool_commands={"bandit": ["bandit"], "semgrep": None, "eslint": None},
        runner=FakeRunner(_bandit_payload()),
    )

    response = await client.get(f"/api/v1/repositories/{repository_id}/sast")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["summary"]["high"] == 1
    assert payload["findings"][0]["rule_id"] == "B602"

    missing = await client.get("/api/v1/repositories/999999/sast")
    assert missing.status_code == 404


async def test_sast_api_rejects_unknown_tool(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "api-tool")
    repository_id = await _create_repository(session_factory, repo)
    app.state.sast_service = SastService(
        session_factory,
        tool_commands={"bandit": None},
        runner=FakeRunner({}),
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/sast",
        params={"tools": "unknown"},
    )
    assert response.status_code == 422
