"""Observability tests: Prometheus metrics and extended health (S8-001..S8-005)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository, RepositoryStatus
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_metrics_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "iiruchating_repositories_total" in body
    assert "iiruchating_fetch_duration_seconds" in body
    assert "iiruchating_status_duration_seconds" in body
    assert "iiruchating_scan_duration_seconds" in body


async def test_metrics_reports_repository_states(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / "repo").resolve()), tracked=True)
        session.add(repository)
        await session.flush()
        session.add(RepositoryStatus(repository_id=repository.id, state="diverged"))
        await session.commit()

    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert 'iiruchating_repositories_total{state="diverged"} 1.0' in response.text


async def test_health_includes_observability_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db_ok"] is True
    assert payload["git_version"]
    assert payload["providers"] == {
        "github": "not_configured",
        "gitflic": "not_configured",
    }
