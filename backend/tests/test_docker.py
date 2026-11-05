"""Docker integration tests (S24-002).

The tests use a fake Docker SDK client, so no Docker daemon is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.entities import Repository
from app.services.docker_service import DockerService
from docker.errors import DockerException
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeContainer:
    def __init__(self, name: str, state: str, attrs: dict[str, Any]) -> None:
        self.id = f"{name}-id-000000000000"
        self.name = name
        self.status = state
        self.attrs = attrs


class FakeContainers:
    def __init__(self, containers: list[FakeContainer]) -> None:
        self._containers = containers
        self.calls = 0

    def list(self, all: bool = True) -> list[FakeContainer]:
        self.calls += 1
        return self._containers


class FakeClient:
    def __init__(self, containers: list[FakeContainer]) -> None:
        self.containers = FakeContainers(containers)
        self.closed = False
        self.pinged = False

    def ping(self) -> bool:
        self.pinged = True
        return True

    def close(self) -> None:
        self.closed = True


class FailingClient:
    def __init__(self) -> None:
        self.closed = False

    def ping(self) -> bool:
        raise DockerException("Docker daemon not running")

    def close(self) -> None:
        self.closed = True


def _container(
    *,
    name: str = "web-1",
    state: str = "running",
    source: str = "C:/Projects/app",
    image: str = "nginx:latest",
    project: str = "app",
) -> FakeContainer:
    attrs: dict[str, Any] = {
        "Config": {
            "Image": image,
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": "web",
                "com.docker.compose.project.working_dir": source,
            },
        },
        "State": {"Status": state},
        "Mounts": [
            {
                "Type": "bind",
                "Source": source,
                "Destination": "/app",
            }
        ],
        "NetworkSettings": {
            "Ports": {
                "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
            }
        },
    }
    if state == "running":
        attrs["State"]["Health"] = {"Status": "healthy"}
    return FakeContainer(name, state, attrs)


async def test_running_container_matches_mount_with_path_map() -> None:
    client = FakeClient([_container()])
    service = DockerService(
        path_map="C:/Projects=/projects",
        client_factory=lambda: client,
    )

    status = await service.get_container_status("/projects/app")

    assert status.status == "running"
    assert status.error is None
    assert len(status.containers) == 1
    container = status.containers[0]
    assert container.name == "web-1"
    assert container.image == "nginx:latest"
    assert container.state == "running"
    assert container.health == "healthy"
    assert container.compose_project == "app"
    assert container.compose_service == "web"
    assert container.match == "mount_source"
    assert container.ports[0].host_port == 8080
    assert container.ports[0].container_port == 80
    assert container.ports[0].protocol == "tcp"
    assert client.closed is True


async def test_path_map_preserves_container_path_case() -> None:
    client = FakeClient(
        [_container(source="D:/Projects/AI/AI-App", project="unrelated")]
    )
    service = DockerService(
        path_map="D:/Projects=/projects",
        client_factory=lambda: client,
    )

    status = await service.get_container_status("/projects/AI/AI-App")

    assert status.status == "running"
    assert status.containers[0].match == "mount_source"


async def test_stopped_container_returns_stopped() -> None:
    service = DockerService(
        path_map="C:/Projects=/projects",
        client_factory=lambda: FakeClient([_container(state="exited")]),
    )

    status = await service.get_container_status("/projects/app")

    assert status.status == "stopped"
    assert status.containers[0].state == "exited"


async def test_no_matching_container_returns_not_found() -> None:
    service = DockerService(
        path_map="C:/Projects=/projects",
        client_factory=lambda: FakeClient(
            [_container(source="C:/Projects/other", project="other")]
        ),
    )

    status = await service.get_container_status("/projects/app")

    assert status.status == "not_found"
    assert status.containers == []
    assert status.error is None


async def test_docker_exception_returns_unavailable() -> None:
    service = DockerService(client_factory=FailingClient)

    status = await service.get_container_status("/projects/app")

    assert status.status == "unavailable"
    assert status.containers == []
    assert status.error == "Docker daemon not running"


async def test_docker_cache_and_refresh() -> None:
    client = FakeClient([_container()])
    service = DockerService(
        path_map="C:/Projects=/projects",
        client_factory=lambda: client,
    )

    await service.get_container_status("/projects/app")
    await service.get_container_status("/projects/app")
    assert client.containers.calls == 1

    await service.get_container_status("/projects/app", refresh=True)
    assert client.containers.calls == 2


async def test_docker_disabled_returns_unavailable() -> None:
    service = DockerService(enabled=False)

    status = await service.get_container_status("/projects/app")

    assert status.status == "unavailable"
    assert status.error == "Docker integration is disabled"


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / "app").resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_docker_api_returns_container_status(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.docker_service = DockerService(
        path_map="C:/Projects=/projects",
        client_factory=lambda: FakeClient([_container()]),
    )

    response = await client.get(f"/api/v1/repositories/{repository_id}/docker")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_id"] == repository_id
    assert payload["status"] == "running"
    assert payload["error"] is None
    assert payload["containers"][0]["name"] == "web-1"
    assert payload["containers"][0]["ports"][0] == {
        "host_ip": "0.0.0.0",
        "host_port": 8080,
        "container_port": 80,
        "protocol": "tcp",
    }
    assert payload["checked_at"]


async def test_docker_api_unavailable_is_not_500(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.docker_service = DockerService(client_factory=FailingClient)

    response = await client.get(f"/api/v1/repositories/{repository_id}/docker")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["error"] == "Docker daemon not running"


async def test_docker_api_missing_repository_returns_404(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/repositories/999999/docker")

    assert response.status_code == 404
