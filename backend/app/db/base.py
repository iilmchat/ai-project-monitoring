"""Database base classes and helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(UTC)
