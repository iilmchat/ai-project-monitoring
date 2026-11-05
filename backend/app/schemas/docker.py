"""Pydantic schemas for the read-only Docker integration (S24-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DockerStatusValue = Literal["running", "stopped", "not_found", "unavailable"]


class DockerPort(BaseModel):
    """Published port of a container."""

    host_ip: str | None = None
    host_port: int | None = None
    container_port: int | None = None
    protocol: str = "tcp"


class DockerContainer(BaseModel):
    """Normalised container information exposed by the API."""

    id: str
    name: str
    image: str
    state: str
    status: str
    health: str | None = None
    ports: list[DockerPort] = Field(default_factory=list)
    compose_project: str | None = None
    compose_service: str | None = None
    match: str = "none"


class DockerStatus(BaseModel):
    """Result of a read-only Docker lookup for one repository."""

    status: DockerStatusValue
    containers: list[DockerContainer] = Field(default_factory=list)
    error: str | None = None


class DockerStatusResponse(DockerStatus):
    """API response for ``GET /repositories/{id}/docker``."""

    repository_id: int
    checked_at: datetime
