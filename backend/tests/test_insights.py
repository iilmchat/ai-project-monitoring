"""Insights tests: git-log parsing, cache, filters and API (S29)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.models.entities import Repository
from app.services.insights_service import (
    GitCommandResult,
    InsightsService,
    is_relevant_path,
    parse_commit_frequency,
    parse_hotspots,
)
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

TODAY = datetime.now().astimezone().date()


class FakeRunner:
    """Deterministic git runner used instead of real subprocesses."""

    def __init__(
        self,
        *,
        branches: set[str] | None = None,
        current_branch: str | None = "main",
        hotspots: str = "",
        frequency: str = "",
        hotspot_result: GitCommandResult | None = None,
        frequency_result: GitCommandResult | None = None,
    ) -> None:
        self.branches = branches if branches is not None else {"main"}
        self.current_branch = current_branch
        self.hotspots = hotspots
        self.frequency = frequency
        self.hotspot_result = hotspot_result
        self.frequency_result = frequency_result
        self.calls: list[list[str]] = []

    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> GitCommandResult:
        self.calls.append(list(args))
        if "rev-parse" in args:
            if "--abbrev-ref" in args:
                if self.current_branch is None:
                    return GitCommandResult(returncode=1)
                return GitCommandResult(
                    returncode=0, stdout=f"{self.current_branch}\n"
                )
            candidate = args[-1]
            if candidate in self.branches:
                return GitCommandResult(returncode=0, stdout=f"{candidate}\n")
            return GitCommandResult(returncode=1)
        if "log" in args:
            if "--name-only" in args:
                return self.hotspot_result or GitCommandResult(
                    returncode=0, stdout=self.hotspots
                )
            if "--format=%ad" in args:
                return self.frequency_result or GitCommandResult(
                    returncode=0, stdout=self.frequency
                )
        return GitCommandResult(returncode=1)


def test_parse_hotspots_counts_and_filters(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.py").write_text("b", encoding="utf-8")
    output = "\n".join(
        [
            "a.py",
            "a.py",
            "a.py",
            "b.py",
            "README.md",
            "package-lock.json",
            "pnpm-lock.yaml",
            "node_modules/pkg/index.js",
            "dist/app.js",
            "missing.py",
        ]
    )

    hotspots = parse_hotspots(output, str(tmp_path), limit=5)

    assert [(item.file, item.count) for item in hotspots] == [
        ("a.py", 3),
        ("b.py", 1),
    ]


def test_parse_hotspots_respects_limit_and_ties(tmp_path: Path) -> None:
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    output = "c.py\nb.py\na.py\n"

    hotspots = parse_hotspots(output, str(tmp_path), limit=2)

    assert [item.file for item in hotspots] == ["a.py", "b.py"]


def test_parse_commit_frequency_fills_gaps() -> None:
    until = TODAY
    first = (until - timedelta(days=2)).isoformat()
    third = until.isoformat()
    output = f"{first}\n{first}\n{third}\nnot-a-date\n"

    points = parse_commit_frequency(output, days=3, until=until)

    assert [point.date for point in points] == [
        (until - timedelta(days=2)).isoformat(),
        (until - timedelta(days=1)).isoformat(),
        third,
    ]
    assert [point.count for point in points] == [2, 0, 1]


def test_is_relevant_path_filters_noise() -> None:
    assert is_relevant_path("backend/app/main.py") is True
    assert is_relevant_path("docs/SPEC.md") is False
    assert is_relevant_path("pnpm-lock.yaml") is False
    assert is_relevant_path("node_modules/react/index.js") is False
    assert is_relevant_path("frontend/dist/app.min.js") is False


async def test_service_builds_report_and_caches(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.py").write_text("b", encoding="utf-8")
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    runner = FakeRunner(
        hotspots="a.py\na.py\nb.py\nREADME.md\n",
        frequency=f"{yesterday}\n{TODAY}\n{TODAY}\n",
    )
    service = InsightsService(runner=runner)

    report = await service.get_report(1, str(tmp_path), days=30)

    assert report.status == "ok"
    assert report.window.branch == "main"
    assert [(item.file, item.count) for item in report.hotspots] == [
        ("a.py", 2),
        ("b.py", 1),
    ]
    assert len(report.commit_frequency) == 30
    assert report.commit_frequency[-1].count == 2
    assert report.summary.commits == 3
    assert report.summary.per_day == 0.1
    assert report.error is None

    runner.calls.clear()
    cached = await service.get_report(1, str(tmp_path), days=30)

    assert cached.summary.commits == 3
    assert runner.calls == []

    await service.get_report(1, str(tmp_path), days=30, refresh=True)

    assert len(runner.calls) == 3


async def test_service_timeout_is_not_an_error_response(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        hotspot_result=GitCommandResult(returncode=-1, timed_out=True),
        frequency_result=GitCommandResult(returncode=-1, timed_out=True),
    )
    service = InsightsService(runner=runner)

    report = await service.get_report(1, str(tmp_path))

    assert report.status == "timeout"
    assert report.error == "timeout"
    assert report.hotspots == []
    assert len(report.commit_frequency) == 30
    assert report.summary.commits == 0


async def test_service_no_branch(tmp_path: Path) -> None:
    runner = FakeRunner(
        branches=set(),
        current_branch=None,
        hotspots="a.py\n",
    )
    service = InsightsService(runner=runner)

    report = await service.get_report(1, str(tmp_path))

    assert report.status == "no_branch"
    assert report.error == "branch_not_found"
    assert report.window.branch is None
    assert report.summary.commits == 0
    assert {call[-1] for call in runner.calls if "rev-parse" in call} == {
        "main",
        "master",
        "HEAD",
    }
    assert not any("--format=%ad" in " ".join(call) for call in runner.calls)


async def test_service_detects_shallow_clone(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "shallow").write_text("abc\n", encoding="utf-8")
    runner = FakeRunner(hotspots="a.py\n", frequency=f"{TODAY}\n")
    service = InsightsService(runner=runner)

    report = await service.get_report(1, str(tmp_path))

    assert report.status == "shallow_clone"
    assert report.error is None


async def test_insights_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    async with session_factory() as session:
        repository = Repository(path=str(tmp_path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        repository_id = repository.id
    app.state.insights_service = InsightsService(
        runner=FakeRunner(
            hotspots="a.py\na.py\n",
            frequency=f"{TODAY}\n",
        )
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/insights"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_id"] == repository_id
    assert payload["status"] == "ok"
    assert payload["hotspots"] == [{"file": "a.py", "count": 2}]
    assert payload["commit_frequency"][-1] == {
        "date": TODAY.isoformat(),
        "count": 1,
    }
    assert payload["summary"]["commits"] == 1


async def test_insights_api_missing_repository(client: AsyncClient) -> None:
    response = await client.get("/api/v1/repositories/999999/insights")

    assert response.status_code == 404


async def test_real_git_history_hotspots_and_frequency(
    make_repo: Callable[[Path], Path], tmp_path: Path
) -> None:
    repo = make_repo(tmp_path / "real")
    git = ["git", "-C", str(repo)]
    identity = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]

    def commit(message: str) -> None:
        subprocess.run(
            [*git, *identity, "add", "-A"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*git, *identity, "commit", "-q", "-m", message],
            check=True,
            capture_output=True,
        )

    (repo / "a.py").write_text("one", encoding="utf-8")
    commit("first")
    (repo / "a.py").write_text("two", encoding="utf-8")
    (repo / "pnpm-lock.yaml").write_text("lock", encoding="utf-8")
    commit("second")
    (repo / "b.py").write_text("b", encoding="utf-8")
    commit("third")

    service = InsightsService()
    report = await service.get_report(1, str(repo), days=30)

    assert report.status == "ok"
    assert report.window.branch == "main"
    assert report.hotspots[0].file == "a.py"
    assert report.hotspots[0].count == 2
    assert all(item.file != "pnpm-lock.yaml" for item in report.hotspots)
    assert report.summary.commits == 3
    assert report.commit_frequency[-1].count == 3
