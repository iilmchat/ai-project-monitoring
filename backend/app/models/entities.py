"""SQLAlchemy 2.0 ORM models (Sprint 1 data model)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Repository(Base):
    """A Git repository discovered on disk."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, index=True, nullable=False)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tracked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    github_full_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    gitflic_full_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    canonical_provider: Mapped[str] = mapped_column(
        String(16), default="github", nullable=False
    )
    mirror_expected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mirror_policy: Mapped[str] = mapped_column(
        String(64), default="github_to_gitflic", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    status: Mapped[RepositoryStatus | None] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        uselist=False,
    )
    mirror: Mapped[RepositoryMirrorStatus | None] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Repository(id={self.id!r}, path={self.path!r}, tracked={self.tracked!r})"


class RepositoryStatus(Base):
    """Latest local status snapshot for a repository (Sprint 2 fills it in)."""

    __tablename__ = "repository_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    head_subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    head_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    upstream: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ahead: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    behind: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_modified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_staged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_untracked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_conflicted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remote_status: Mapped[str] = mapped_column(String(32), default="stale", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="status")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"RepositoryStatus(repository_id={self.repository_id!r}, state={self.state!r})"


class RepositoryMirrorStatus(Base):
    """Latest cross-provider (GitHub ↔ GitFlic) snapshot for a repository."""

    __tablename__ = "repository_mirror_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    github_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gitflic_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    github_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gitflic_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gitflic_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mirror_status: Mapped[str] = mapped_column(
        String(32), default="unavailable", nullable=False
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="mirror")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"RepositoryMirrorStatus(repository_id={self.repository_id!r}, "
            f"mirror_status={self.mirror_status!r})"
        )


class WebhookEvent(Base):
    """Incoming GitHub/GitFlic webhook (SPEC §4, R9)."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="received", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"WebhookEvent(provider={self.provider!r}, event_type={self.event_type!r})"


class AppSetting(Base):
    """Key/value application settings persisted in the database (S15-001)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"AppSetting(key={self.key!r})"


class DependencyCache(Base):
    """TTL cache for registry latest-version lookups (SPEC §4, S25-001)."""

    __tablename__ = "dependency_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    ecosystem: Mapped[str] = mapped_column(String(16), nullable=False)
    package: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"DependencyCache(key={self.key!r}, "
            f"latest_version={self.latest_version!r})"
        )


class SecurityCache(Base):
    """TTL cache for OSV.dev advisories keyed by package version (SPEC §4, S28)."""

    __tablename__ = "security_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    ecosystem: Mapped[str] = mapped_column(String(16), nullable=False)
    package: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"SecurityCache(key={self.key!r}, package={self.package!r}, "
            f"version={self.version!r})"
        )


class AIProviderProfile(Base):
    """OpenAI-compatible AI provider profile (S39-001)."""

    __tablename__ = "ai_provider_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"AIProviderProfile(id={self.id!r}, name={self.name!r})"


class AICache(Base):
    """TTL cache for LLM-generated explanations (SPEC §4, S33)."""

    __tablename__ = "ai_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"AICache(key={self.key!r}, kind={self.kind!r})"


class ActionLog(Base):
    """Audit trail for explicitly confirmed mutations (SPEC §3.7, S10-005)."""

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(64), default="local", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ActionLog(action={self.action!r}, status={self.status!r})"


class ScanRun(Base):
    """History of discovery scans."""

    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    roots: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ScanRun(id={self.id!r}, status={self.status!r})"


__all__ = [
    "AICache",
    "AIProviderProfile",
    "ActionLog",
    "AppSetting",
    "DependencyCache",
    "Repository",
    "RepositoryMirrorStatus",
    "RepositoryStatus",
    "ScanRun",
    "SecurityCache",
    "WebhookEvent",
]
