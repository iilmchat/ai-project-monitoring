"""SQLAlchemy 2.0 ORM models (Sprint 1 data model)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Repository(Base):
    """A Git repository discovered on disk."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, index=True, nullable=False)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tracked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
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
    ahead: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    behind: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_modified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_staged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dirty_untracked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="status")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"RepositoryStatus(repository_id={self.repository_id!r}, state={self.state!r})"


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


__all__ = ["Repository", "RepositoryStatus", "ScanRun"]
