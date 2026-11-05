"""Read-only Docker container lookup for a repository (S24-002).

The service deliberately never starts, stops, restarts or execs containers.
Docker SDK calls are synchronous, so the blocking part runs in a worker thread.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import docker
from docker.errors import DockerException

from app.schemas.docker import (
    DockerContainer,
    DockerPort,
    DockerStatus,
    DockerStatusValue,
)

ClientFactory = Callable[[], Any]
PathMapping = list[tuple[str, str]]

_CONTAINER_RUNNING_STATES = {"running", "restarting"}


def _normalize_path(value: str) -> str:
    """Normalise Windows/Unix paths for comparisons."""
    normalized = value.strip().replace("\\", "/")
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    if not normalized:
        return "/"
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        normalized = normalized.lower()
    return normalized


def _parse_path_map(raw: str | None) -> PathMapping:
    """Parse ``host=container,host2=container2`` into normalised pairs."""
    mappings: PathMapping = []
    if not raw:
        return mappings
    for chunk in raw.split(","):
        if "=" not in chunk:
            continue
        host, container = chunk.split("=", 1)
        host = host.strip()
        container = container.strip()
        if host and container:
            mappings.append((_normalize_path(host), _normalize_path(container)))
    return mappings


def _apply_path_map(value: str, mappings: PathMapping) -> str:
    """Translate a host path to the container namespace when a mapping exists.

    The host part is compared case-insensitively on Windows, but the suffix
    keeps its original case because Linux container paths are case-sensitive.
    """
    raw = value.strip().replace("\\", "/")
    if len(raw) > 1:
        raw = raw.rstrip("/")
    normalized = _normalize_path(raw)
    comparable = (
        raw.lower()
        if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha()
        else raw
    )

    for host, container in mappings:
        if comparable == host or comparable.startswith(f"{host}/"):
            suffix = raw[len(host) :]
            return _normalize_path(f"{container}{suffix}")
    return normalized


def _repository_slug(repo_path: str) -> str:
    normalized = repo_path.strip().replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1].lower()


def _extract_ports(attrs: dict[str, Any]) -> list[DockerPort]:
    network = attrs.get("NetworkSettings")
    if not isinstance(network, dict):
        return []
    raw_ports = network.get("Ports")
    if not isinstance(raw_ports, dict):
        return []

    ports: list[DockerPort] = []
    for key, bindings in raw_ports.items():
        if not isinstance(key, str):
            continue
        container_raw, _, protocol = key.partition("/")
        try:
            container_port = int(container_raw)
        except ValueError:
            continue

        if not isinstance(bindings, list) or not bindings:
            ports.append(
                DockerPort(
                    container_port=container_port,
                    protocol=protocol or "tcp",
                )
            )
            continue

        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_raw = binding.get("HostPort")
            if isinstance(host_raw, int):
                host_port = host_raw
            elif isinstance(host_raw, str) and host_raw:
                try:
                    host_port = int(host_raw)
                except ValueError:
                    host_port = None
            else:
                host_port = None
            host_ip = binding.get("HostIp")
            ports.append(
                DockerPort(
                    host_ip=str(host_ip) if host_ip else None,
                    host_port=host_port,
                    container_port=container_port,
                    protocol=protocol or "tcp",
                )
            )

    return sorted(
        ports,
        key=lambda port: (
            port.container_port if port.container_port is not None else 0,
            port.protocol,
            port.host_port if port.host_port is not None else 0,
        ),
    )


def _container_info(container: Any, match: str) -> DockerContainer:
    attrs: dict[str, Any] = getattr(container, "attrs", {}) or {}
    state_data = attrs.get("State")
    if not isinstance(state_data, dict):
        state_data = {}

    state = str(state_data.get("Status") or getattr(container, "status", "unknown"))
    health_data = state_data.get("Health")
    health: str | None = None
    if isinstance(health_data, dict):
        raw_health = health_data.get("Status")
        health = str(raw_health) if raw_health else None

    config = attrs.get("Config")
    if not isinstance(config, dict):
        config = {}
    image = str(config.get("Image") or "")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        labels = {}

    status_text = f"{state} ({health})" if health else state
    return DockerContainer(
        id=str(getattr(container, "id", ""))[:12],
        name=str(getattr(container, "name", "") or ""),
        image=image,
        state=state,
        status=status_text,
        health=health,
        ports=_extract_ports(attrs),
        compose_project=_optional_str(labels.get("com.docker.compose.project")),
        compose_service=_optional_str(labels.get("com.docker.compose.service")),
        match=match,
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value else None


def _unavailable_message(exc: Exception) -> str:
    text = str(exc).lower()
    if "permission denied" in text or "access is denied" in text:
        return "Docker daemon permission denied"
    if (
        "not running" in text
        or "cannot connect" in text
        or "connection" in text
        or "no such file" in text
        or "not found" in text
        or "pipe" in text
        or "daemon" in text
    ):
        return "Docker daemon not running"
    return "Docker daemon not available"


class DockerService:
    """Look up containers that use a repository directory (read-only)."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        host: str | None = None,
        path_map: str | None = None,
        timeout_seconds: float = 3.0,
        cache_ttl_seconds: int = 30,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._enabled = enabled
        self._host = host or None
        self._path_map = _parse_path_map(path_map)
        self._timeout = max(timeout_seconds, 0.1)
        self._ttl = max(cache_ttl_seconds, 0)
        self._client_factory = client_factory
        self._cache: dict[str, tuple[float, DockerStatus]] = {}

    async def get_container_status(
        self,
        repo_path: str,
        *,
        refresh: bool = False,
    ) -> DockerStatus:
        """Return the container status for ``repo_path`` without mutating Docker."""
        if not self._enabled:
            return DockerStatus(
                status="unavailable",
                error="Docker integration is disabled",
            )

        cache_key = _normalize_path(repo_path)
        now = time.monotonic()
        if not refresh:
            cached = self._cache.get(cache_key)
            if cached is not None and now - cached[0] < self._ttl:
                return cached[1]

        result = await asyncio.to_thread(self._collect, repo_path)
        self._cache[cache_key] = (time.monotonic(), result)
        return result

    def _collect(self, repo_path: str) -> DockerStatus:
        client: Any | None = None
        try:
            client = self._build_client()
            client.ping()
            containers = client.containers.list(all=True)
        except DockerException as exc:
            return DockerStatus(status="unavailable", error=_unavailable_message(exc))
        except Exception as exc:  # requests/connection errors are not always wrapped
            return DockerStatus(status="unavailable", error=_unavailable_message(exc))
        finally:
            if client is not None:
                with suppress(Exception):
                    client.close()

        matched: list[DockerContainer] = []
        for container in containers:
            match = self._match(container, repo_path)
            if match is not None:
                matched.append(_container_info(container, match))

        if not matched:
            return DockerStatus(status="not_found")
        status: DockerStatusValue = (
            "running"
            if any(item.state in _CONTAINER_RUNNING_STATES for item in matched)
            else "stopped"
        )
        return DockerStatus(status=status, containers=matched)

    def _build_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        if self._host:
            return docker.DockerClient(base_url=self._host, timeout=self._timeout)
        return docker.from_env(timeout=self._timeout)

    def _candidate_paths(self, repo_path: str) -> set[str]:
        return {
            _normalize_path(repo_path),
            _normalize_path(_apply_path_map(repo_path, self._path_map)),
        }

    def _path_matches(self, value: str, candidates: set[str]) -> bool:
        if _normalize_path(value) in candidates:
            return True
        mapped = _apply_path_map(value, self._path_map)
        return _normalize_path(mapped) in candidates

    def _match(self, container: Any, repo_path: str) -> str | None:
        attrs: dict[str, Any] = getattr(container, "attrs", {}) or {}
        candidates = self._candidate_paths(repo_path)

        mounts = attrs.get("Mounts")
        if isinstance(mounts, list):
            for mount in mounts:
                if not isinstance(mount, dict):
                    continue
                # Named volumes are not bind mounts to a repository directory.
                if mount.get("Type") not in (None, "bind"):
                    continue
                source = mount.get("Source")
                if isinstance(source, str) and source and self._path_matches(source, candidates):
                    return "mount_source"
                destination = mount.get("Destination")
                if (
                    isinstance(destination, str)
                    and destination
                    and self._path_matches(destination, candidates)
                ):
                    return "mount_destination"

        config = attrs.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if isinstance(labels, dict):
            working_dir = labels.get("com.docker.compose.project.working_dir")
            if (
                isinstance(working_dir, str)
                and working_dir
                and self._path_matches(working_dir, candidates)
            ):
                return "compose_workdir"

            project = labels.get("com.docker.compose.project")
            slug = _repository_slug(repo_path)
            if isinstance(project, str) and project and project.lower() == slug:
                return "compose_project"

        slug = _repository_slug(repo_path)
        if slug:
            name = str(getattr(container, "name", "") or "").lower()
            if slug in name:
                return "name"
            image = str(config.get("Image") or "").lower() if isinstance(config, dict) else ""
            if slug in image:
                return "image"

        return None
