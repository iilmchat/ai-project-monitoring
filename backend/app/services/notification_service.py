"""Desktop notifications (S11-002).

Notifications are best-effort: missing desktop backends must never break the
application. Delivery is disabled with ``NOTIFICATIONS_ENABLED=false``.
"""

from __future__ import annotations

import time

import structlog

logger = structlog.get_logger(__name__)

REMOTE_ERROR_INTERVAL_SECONDS = 3600


class NotificationService:
    """Small wrapper around ``plyer`` with per-event rate limiting."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        notify_on: set[str] | None = None,
        remote_error_interval_seconds: int = REMOTE_ERROR_INTERVAL_SECONDS,
    ) -> None:
        self._enabled = enabled
        self._notify_on = notify_on or set()
        self._remote_interval = remote_error_interval_seconds
        self._last_remote_notification: dict[int, float] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def notify_on(self) -> set[str]:
        return self._notify_on

    def send_notification(self, title: str, message: str) -> bool:
        if not self._enabled:
            return False
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                app_name="ai-project-monitoring",
                timeout=10,
            )
        except Exception:
            logger.warning("notification_failed", title=title)
            return False
        logger.info("notification_sent", title=title)
        return True

    def notify_mirror_status(
        self,
        repository_id: int,
        repository_path: str,
        mirror_status: str,
        previous_status: str | None,
    ) -> bool:
        """Notify when a mirror status transition is configured in NOTIFY_ON."""
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
        """Notify about a remote error at most once per hour per repository."""
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


__all__ = ["REMOTE_ERROR_INTERVAL_SECONDS", "NotificationService"]
