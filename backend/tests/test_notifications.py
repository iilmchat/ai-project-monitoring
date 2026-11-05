"""Desktop notification tests (S11-002)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.models.entities import Repository
from app.services.mirror_scheduler import MirrorScheduler
from app.services.mirror_service import MirrorSnapshot
from app.services.notification_service import NotificationService
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def sent(monkeypatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_notify(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("plyer.notification.notify", fake_notify)
    return calls


def test_send_notification_calls_plyer(sent) -> None:
    service = NotificationService(enabled=True)

    assert service.send_notification("Title", "Message") is True
    assert len(sent) == 1
    assert sent[0]["title"] == "Title"
    assert sent[0]["message"] == "Message"


def test_notifications_disabled(sent) -> None:
    service = NotificationService(enabled=False)

    assert service.send_notification("Title", "Message") is False
    assert sent == []


def test_notify_on_transition(sent) -> None:
    service = NotificationService(
        enabled=True, notify_on={"history_rewritten", "missing_on_gitflic"}
    )

    assert service.notify_mirror_status(1, "C:/repo", "in_sync", None) is False
    assert (
        service.notify_mirror_status(1, "C:/repo", "history_rewritten", "in_sync")
        is True
    )
    assert (
        service.notify_mirror_status(
            1, "C:/repo", "history_rewritten", "history_rewritten"
        )
        is False
    )
    assert len(sent) == 1


def test_remote_error_is_rate_limited(sent) -> None:
    service = NotificationService(enabled=True)

    assert service.notify_remote_unavailable(1, "C:/repo", "network") is True
    assert service.notify_remote_unavailable(1, "C:/repo", "network") is False
    assert len(sent) == 1


class FakeMirrorService:
    enabled = True

    def __init__(self) -> None:
        self.status = "in_sync"

    async def refresh_mirror_status(self, repository: Repository) -> MirrorSnapshot:
        return MirrorSnapshot(
            repository_id=repository.id,
            mirror_status=self.status,
            canonical_provider="github",
            mirror_expected=True,
            github=None,
            gitflic=None,
            recommendations=[],
            checked_at=datetime.now(UTC),
        )


async def test_scheduler_notifies_on_transition(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    sent,
) -> None:
    async with session_factory() as session:
        session.add(
            Repository(
                path=str((tmp_path / "repo").resolve()),
                tracked=True,
                github_full_name="acme/app",
            )
        )
        await session.commit()

    fake = FakeMirrorService()
    notifications = NotificationService(enabled=True, notify_on={"history_rewritten"})
    scheduler = MirrorScheduler(fake, session_factory, notifications=notifications)  # type: ignore[arg-type]

    await scheduler.tick()
    assert sent == []

    fake.status = "history_rewritten"
    await scheduler.tick()
    assert len(sent) == 1
