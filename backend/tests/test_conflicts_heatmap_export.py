"""Conflicts, heatmap and export endpoint tests (S21-002, S21-004, S21-005)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository, RepositoryStatus
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    name: str,
    *,
    state: str = "current",
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str((tmp_path / name).resolve()),
            tracked=True,
            github_full_name=f"acme/{name}",
        )
        session.add(repository)
        await session.flush()
        session.add(
            RepositoryStatus(
                repository_id=repository.id,
                state=state,
                branch="main",
                remote_status="ok",
            )
        )
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_conflicts_endpoint(
    app,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository_id = await _create_repository(
        session_factory, tmp_path, "conflicts", state="diverged"
    )
    monkeypatch.setattr(
        "app.api.v1.repositories.get_conflicts",
        lambda path: ["src/app.py", "README.md"],
    )

    response = await client.get(f"/api/v1/repositories/{repository_id}/conflicts")

    assert response.status_code == 200
    assert response.json() == {
        "repository_id": repository_id,
        "files": ["src/app.py", "README.md"],
    }


async def test_heatmap_aggregates_commit_dates(
    app,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    await _create_repository(session_factory, tmp_path, "one")
    await _create_repository(session_factory, tmp_path, "two")

    def fake_commit_dates(path: str, since: str, timeout: float = 30) -> list[str]:
        if path.endswith("one"):
            return ["2026-11-01", "2026-11-02"]
        return ["2026-11-02"]

    monkeypatch.setattr("app.api.v1.activity.commit_dates", fake_commit_dates)

    response = await client.get("/api/v1/dashboard/heatmap", params={"days": 30})

    assert response.status_code == 200
    assert response.json() == {"2026-11-01": 1, "2026-11-02": 2}


async def test_export_json_and_csv(
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_repository(session_factory, tmp_path, "alpha")
    await _create_repository(session_factory, tmp_path, "beta", state="dirty")

    json_response = await client.get("/api/v1/repositories/export")
    assert json_response.status_code == 200
    payload = json_response.json()
    assert len(payload) == 2
    assert {row["state"] for row in payload} == {"current", "dirty"}
    assert "attachment" in json_response.headers["content-disposition"]

    csv_response = await client.get(
        "/api/v1/repositories/export", params={"format": "csv"}
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    lines = csv_response.text.strip().splitlines()
    assert lines[0].startswith("id,path,alias,tracked,state")
    assert len(lines) == 3
