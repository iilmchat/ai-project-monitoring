"""Notifications via Telegram with logger fallback (S21-003)."""

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


class FakeResponse:
    status_code = 200


class FakeTelegramClient:
    def __init__(self, calls: list[tuple[str, dict[str, object]]]) -> None:
        self._calls = calls

    def __enter__(self) -> FakeTelegramClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        self._calls.append((url, json))
        return FakeResponse()


@pytest.fixture
def telegram_calls(monkeypatch) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.services.notification_service.httpx.Client",
        lambda timeout: FakeTelegramClient(calls),
    )
    return calls


def test_send_notification_via_telegram(telegram_calls) -> None:
    service = NotificationService(
        enabled=True, bot_token="123:abc", chat_id="42"
    )

    assert service.send_notification("Title", "Message") is True
    assert len(telegram_calls) == 1
    url, payload = telegram_calls[0]
    assert "/bot123:abc/sendMessage" in url
    assert payload["chat_id"] == "42"
    assert "Title" in str(payload["text"])


def test_logger_fallback_without_telegram(telegram_calls) -> None:
    service = NotificationService(enabled=True)

    assert service.send_notification("Title", "Message") is True
    assert telegram_calls == []


def test_notifications_disabled(telegram_calls) -> None:
    service = NotificationService(enabled=False, bot_token="123:abc", chat_id="42")

    assert service.send_notification("Title", "Message") is False
    assert telegram_calls == []


def test_notify_on_transition() -> None:
    service = NotificationService(
        enabled=True, notify_on={"history_rewritten", "missing_on_gitflic"}
    )
    calls: list[tuple[str, str]] = []
    service._deliver = lambda title, message: calls.append((title, message)) or True  # type: ignore[method-assign]

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
    assert len(calls) == 1


def test_remote_error_is_rate_limited() -> None:
    service = NotificationService(enabled=True)
    calls: list[str] = []
    service._deliver = lambda title, message: calls.append(title) or True  # type: ignore[method-assign]

    assert service.notify_remote_unavailable(1, "C:/repo", "network") is True
    assert service.notify_remote_unavailable(1, "C:/repo", "network") is False
    assert len(calls) == 1


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
    calls: list[str] = []
    notifications._deliver = lambda title, message: calls.append(title) or True  # type: ignore[method-assign]
    scheduler = MirrorScheduler(fake, session_factory, notifications=notifications)  # type: ignore[arg-type]

    await scheduler.tick()
    assert calls == []

    fake.status = "history_rewritten"
    await scheduler.tick()
    assert len(calls) == 1
