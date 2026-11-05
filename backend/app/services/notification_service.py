"""Notifications via Telegram Bot API with logger fallback (S21-003).

Desktop ``plyer`` notifications were removed: they do not work in Docker and
other headless environments (KI-007). Telegram is used when configured;
otherwise events are written to the structured log.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import structlog

logger = structlog.get_logger(__name__)

REMOTE_ERROR_INTERVAL_SECONDS = 3600
TELEGRAM_API = "https://api.telegram.org"


class NotificationService:
    """Send notifications to Telegram (or log) with per-event rate limiting."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        notify_on: set[str] | None = None,
        bot_token: str = "",
        chat_id: str = "",
        remote_error_interval_seconds: int = REMOTE_ERROR_INTERVAL_SECONDS,
        http_timeout: float = 10.0,
    ) -> None:
        self._enabled = enabled
        self._notify_on = notify_on or set()
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._remote_interval = remote_error_interval_seconds
        self._http_timeout = http_timeout
        self._last_remote_notification: dict[int, float] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def notify_on(self) -> set[str]:
        return self._notify_on

    @property
    def telegram_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    def send_notification(self, title: str, message: str) -> bool:
        if not self._enabled:
            return False
        return self._deliver(title, message)

    def _deliver(self, title: str, message: str) -> bool:
        if not self.telegram_configured:
            logger.info("notification_logged", title=title, message=message)
            return True

        try:
            with httpx.Client(timeout=self._http_timeout) as client:
                response = client.post(
                    f"{TELEGRAM_API}/bot{self._bot_token}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": f"{title}\n{message}",
                        "disable_web_page_preview": True,
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning("notification_failed", title=title, error=str(exc))
            return False

        if response.status_code >= 400:
            logger.warning(
                "notification_failed",
                title=title,
                status_code=response.status_code,
            )
            return False
        logger.info("notification_sent", title=title, channel="telegram")
        return True

    def notify_mirror_status(
        self,
        repository_id: int,
        repository_path: str,
        mirror_status: str,
        previous_status: str | None,
    ) -> bool:
        if previous_status is None or previous_status == mirror_status:
            return False
        if mirror_status not in self._notify_on:
            return False
        return self.send_notification(
            title=f"Mirror: {mirror_status}",
            message=f"{repository_path}\n{previous_status} → {mirror_status}",
        )

    def notify_remote_unavailable(
        self,
        repository_id: int,
        repository_path: str,
        error: str | None = None,
    ) -> bool:
        now = time.monotonic()
        last = self._last_remote_notification.get(repository_id)
        if last is not None and (now - last) < self._remote_interval:
            return False
        self._last_remote_notification[repository_id] = now
        detail = f"\n{error}" if error else ""
        return self.send_notification(
            title="Remote unavailable",
            message=f"{repository_path}\nremote_status=unavailable{detail}",
        )


NotificationSender = Callable[[str, str], bool]

__all__ = ["REMOTE_ERROR_INTERVAL_SECONDS", "NotificationService"]
