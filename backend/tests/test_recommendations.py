"""Recommendation service and API tests (S5-001, S5-002)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models.entities import Repository, RepositoryStatus
from app.schemas.repository import DirtyCountsResponse, RepositoryStatusResponse
from app.services.recommendation_service import generate_recommendations
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def make_status(**overrides: object) -> RepositoryStatusResponse:
    data: dict[str, object] = {
        "repository_id": 1,
        "path": "C:/work/repo",
        "branch": "main",
        "head_sha": "abc123",
        "head_subject": "init",
        "head_date": datetime.now(UTC),
        "upstream": "origin/main",
        "ahead": 0,
        "behind": 0,
        "state": "current",
        "dirty": DirtyCountsResponse(),
        "detached": False,
        "remote_status": "ok",
        "error": None,
        "checked_at": datetime.now(UTC),
    }
    data.update(overrides)
    return RepositoryStatusResponse.model_validate(data)


def _actions(status: RepositoryStatusResponse) -> list[str]:
    return [item.action for item in generate_recommendations(status)]


def test_dirty_recommends_commit_and_stash() -> None:
    status = make_status(state="dirty", dirty=DirtyCountsResponse(modified=2))
    recommendations = generate_recommendations(status)

    assert _actions(status) == ["commit", "stash"]
    assert recommendations[0].command.startswith("git add . && git commit")
    assert recommendations[1].command == "git stash"
    assert all(item.category == "local" for item in recommendations)


def test_diverged_recommends_rebase() -> None:
    status = make_status(state="diverged", ahead=1, behind=2)
    recommendations = generate_recommendations(status)

    assert _actions(status) == ["pull-rebase", "merge"]
    assert recommendations[0].command == "git pull --rebase origin main"


def test_ahead_recommends_push() -> None:
    status = make_status(state="ahead", ahead=2)
    assert generate_recommendations(status)[0].command == "git push origin main"


def test_behind_recommends_pull() -> None:
    status = make_status(state="behind", behind=2)
    assert generate_recommendations(status)[0].command == "git pull origin main"


def test_no_upstream_recommends_set_upstream() -> None:
    status = make_status(state="no_upstream", upstream=None)
    recommendations = generate_recommendations(status)

    assert _actions(status) == ["set-upstream"]
    assert recommendations[0].command == (
        "git branch --set-upstream-to=origin/main main"
    )


def test_current_has_no_recommendations() -> None:
    assert generate_recommendations(make_status()) == []


async def _add_repository_with_status(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    name: str,
    *,
    state: str,
    branch: str = "main",
    upstream: str | None = "origin/main",
    ahead: int = 0,
    behind: int = 0,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / name).resolve()), tracked=True)
        session.add(repository)
        await session.flush()
        session.add(
            RepositoryStatus(
                repository_id=repository.id,
                state=state,
                branch=branch,
                upstream=upstream,
                ahead=ahead,
                behind=behind,
                remote_status="ok",
            )
        )
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_recommendations_api(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    repository_id = await _add_repository_with_status(
        session_factory, tmp_path, "dirty", state="dirty"
    )

    response = await client.get(f"/api/v1/repositories/{repository_id}/recommendations")
    assert response.status_code == 200
    payload = response.json()
    assert [item["action"] for item in payload] == ["commit", "stash"]
    assert payload[0]["reason"]
    assert payload[0]["command"]
    assert payload[0]["category"] == "local"


async def test_recommendations_api_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/repositories/999999/recommendations")
    assert response.status_code == 404
