"""Append-only audit trail (v1.3.0, Sprint 58).

The service records security-relevant actions (scan, mutations, settings and
user management). It intentionally stores only metadata: no tokens, passwords,
file contents or diffs.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.models.entities import AuditLog, User

logger = structlog.get_logger(__name__)

_MAX_DETAILS_CHARS = 4000


class AuditService:
    """Write and read the append-only ``audit_log`` table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def log(
        self,
        user_id: int | None,
        action: str,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Persist one audit entry without leaking secrets."""
        safe_details = _safe_details(details or {})
        async with self._session_factory() as session:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=None if entity_id is None else str(entity_id),
                details=safe_details,
                created_at=utcnow(),
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        logger.info(
            "audit_logged",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
        )
        return entry

    async def list_entries(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AuditLog, str | None]], int]:
        """Return one page of entries plus the total count (newest first)."""
        statement = (
            select(AuditLog, User.username)
            .outerjoin(User, AuditLog.user_id == User.id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await session.execute(statement)).all()
        total = await session.scalar(select(func.count()).select_from(AuditLog))
        return [(row[0], row[1]) for row in rows], int(total or 0)


def _safe_details(details: dict[str, Any]) -> dict[str, Any]:
    """Keep metadata only and cap the payload size."""
    allowed: dict[str, Any] = {}
    for key, value in details.items():
        if not isinstance(key, str) or not key:
            continue
        if not isinstance(value, str | int | float | bool | list | dict | type(None)):
            continue
        allowed[key] = value
    try:
        encoded = json.dumps(allowed, ensure_ascii=False)
    except (TypeError, ValueError):
        return {}
    if len(encoded) > _MAX_DETAILS_CHARS:
        return {"truncated": True}
    return allowed


__all__ = ["AuditService"]
