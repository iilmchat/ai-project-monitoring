"""Dashboard aggregation and track/untrack tests (S4-001, S4-003)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository, RepositoryMirrorStatus, RepositoryStatus
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _add_repository(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    name: str,
    *,
    tracked: bool,
    state: str | None = None,
    remote_status: str = "ok",
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / name).resolve()), tracked=tracked)
        session.add(repository)
        await session.flush()
        if state is not None:
            session.add(
                RepositoryStatus(
                    repository_id=repository.id,
                    state=state,
                    remote_status=remote_status,
                )
            )
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def _seed_dashboard(session_factory, tmp_path: Path) -> dict[str, int]:
    return {
        "current": await _add_repository(
            session_factory, tmp_path, "current", tracked=True, state="current"
        ),
        "dirty": await _add_repository(
            session_factory, tmp_path, "dirty", tracked=True, state="dirty", remote_status="stale"
        ),
        "behind": await _add_repository(
            session_factory,
            tmp_path,
            "behind",
            tracked=True,
            state="behind",
            remote_status="unavailable",
        ),
        "no_upstream": await _add_repository(
            session_factory,
            tmp_path,
            "no-upstream",
            tracked=True,
            state="no_upstream",
            remote_status="stale",
        ),
        "error": await _add_repository(
            session_factory,
            tmp_path,
            "broken",
            tracked=True,
            state="error",
            remote_status="unavailable",
        ),
        "untracked": await _add_repository(
            session_factory, tmp_path, "untracked", tracked=False, state="current"
        ),
        "no_status": await _add_repository(
            session_factory, tmp_path, "no-status", tracked=True, state=None
        ),
    }


async def test_dashboard_aggregation(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    ids = await _seed_dashboard(session_factory, tmp_path)

    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"] == {
        "total": 7,
        "clean": 2,
        "needs_attention": 3,
        "untracked": 1,
        "stale": 4,
        "errors": 1,
        "mirror_issues": 0,
        "by_state": {
            "current": 2,
            "dirty": 1,
            "behind": 1,
            "no_upstream": 1,
            "error": 1,
        },
        "by_mirror_status": {},
    }
    assert len(payload["repositories"]) == 7

    by_path = {
        item["path"].replace("\\", "/").rsplit("/", 1)[-1]: item
        for item in payload["repositories"]
    }
    assert by_path["current"]["status"]["state"] == "current"
    assert by_path["broken"]["status"]["state"] == "error"
    assert by_path["no-status"]["status"] is None
    assert by_path["untracked"]["tracked"] is False
    assert {item["id"] for item in payload["repositories"]} == set(ids.values())


async def test_dashboard_tracked_only(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    await _seed_dashboard(session_factory, tmp_path)

    response = await client.get("/api/v1/dashboard", params={"tracked_only": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == 6
    assert payload["summary"]["untracked"] == 0
    assert all(item["tracked"] for item in payload["repositories"])


async def test_track_and_untrack(session_factory, client: AsyncClient, tmp_path: Path) -> None:
    repository_id = await _add_repository(
        session_factory, tmp_path, "picker", tracked=False, state="current"
    )

    tracked = await client.post(f"/api/v1/repositories/{repository_id}/track")
    assert tracked.status_code == 200
    assert tracked.json()["tracked"] is True

    dashboard = await client.get("/api/v1/dashboard")
    assert dashboard.json()["summary"]["untracked"] == 0

    untracked = await client.post(f"/api/v1/repositories/{repository_id}/untrack")
    assert untracked.status_code == 200
    assert untracked.json()["tracked"] is False

    missing = await client.post("/api/v1/repositories/999999/track")
    assert missing.status_code == 404


async def test_dashboard_includes_mirror_issues(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    repository_id = await _add_repository(
        session_factory, tmp_path, "mirror", tracked=True, state="current"
    )
    async with session_factory() as session:
        session.add(
            RepositoryMirrorStatus(
                repository_id=repository_id,
                mirror_status="behind_gitflic",
                details={},
            )
        )
        await session.commit()

    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["mirror_issues"] == 1
    item = next(row for row in payload["repositories"] if row["id"] == repository_id)
    assert item["mirror"]["mirror_status"] == "behind_gitflic"


async def test_dashboard_cors_preflight(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/dashboard",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
