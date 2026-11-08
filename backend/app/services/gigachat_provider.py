"""GigaChat OAuth provider (S43-002).

The OAuth token is cached in memory per profile and refreshed under a
single-flight lock. Secrets and tokens are never written to logs.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models.entities import AIProviderProfile

logger = structlog.get_logger(__name__)

DEFAULT_SCOPE = "GIGACHAT_API_PERS"
DEFAULT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"


class GigaChatError(Exception):
    """Domain error with a stable machine-readable code."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True, slots=True)
class GigaChatToken:
    access_token: str
    expires_at: datetime


class GigaChatProvider:
    """OAuth 2.0 token manager and chat client for GigaChat."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._session_factory = session_factory
        self._tokens: dict[int, GigaChatToken] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._verify: bool | str = (
            settings.gigachat_ca_bundle or True
        )

    def invalidate(self, profile_id: int) -> None:
        self._tokens.pop(profile_id, None)

    def remember(self, profile_id: int, token: GigaChatToken) -> None:
        self._tokens[profile_id] = token

    async def authorize(
        self,
        client_id: str,
        client_secret: str,
        scope: str = DEFAULT_SCOPE,
    ) -> GigaChatToken:
        if not client_id.strip() or not client_secret.strip():
            raise GigaChatError("invalid_client", "client_id/client_secret required")
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {credentials}",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.gigachat_timeout_seconds,
                transport=self._transport,
                verify=self._verify,
            ) as client:
                response = await client.post(
                    self._settings.gigachat_oauth_url,
                    data={"scope": scope or DEFAULT_SCOPE},
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise GigaChatError("timeout", "GigaChat OAuth timed out") from exc
        except httpx.HTTPError as exc:
            raise GigaChatError(
                "provider_unavailable", "GigaChat OAuth connection failed"
            ) from exc

        if response.status_code >= 400:
            code = _oauth_error_code(response)
            raise GigaChatError(code, f"GigaChat OAuth failed: {code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise GigaChatError("invalid_response", "invalid OAuth JSON") from exc
        if not isinstance(body, dict):
            raise GigaChatError("invalid_response", "invalid OAuth payload")
        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GigaChatError("invalid_response", "access_token missing")
        expires_at = _parse_expires_at(body)
        return GigaChatToken(access_token=access_token, expires_at=expires_at)

    async def get_token(
        self,
        profile: AIProviderProfile,
        *,
        force: bool = False,
    ) -> str:
        if not force:
            cached = self._tokens.get(profile.id)
            if cached is not None and self._is_valid(cached):
                return cached.access_token
            stored = self._token_from_profile(profile)
            if stored is not None and self._is_valid(stored):
                self._tokens[profile.id] = stored
                return stored.access_token

        lock = self._locks.setdefault(profile.id, asyncio.Lock())
        async with lock:
            if not force:
                cached = self._tokens.get(profile.id)
                if cached is not None and self._is_valid(cached):
                    return cached.access_token
            token = await self.authorize(
                profile.client_id or "",
                profile.client_secret or "",
                profile.oauth_scope or self._settings.gigachat_scope or DEFAULT_SCOPE,
            )
            self._tokens[profile.id] = token
            await self._persist_token(profile.id, token)
            return token.access_token

    async def complete(
        self,
        profile: AIProviderProfile,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        token = await self.get_token(profile)
        response = await self._chat_request(profile, payload, token)
        if response.status_code == 401:
            self.invalidate(profile.id)
            token = await self.get_token(profile, force=True)
            response = await self._chat_request(profile, payload, token)
        if response.status_code >= 400:
            raise GigaChatError(f"http_{response.status_code}", "GigaChat request failed")
        try:
            body = response.json()
        except ValueError as exc:
            raise GigaChatError("invalid_response", "invalid chat JSON") from exc
        if not isinstance(body, dict):
            raise GigaChatError("invalid_response", "invalid chat payload")
        return body

    async def _chat_request(
        self,
        profile: AIProviderProfile,
        payload: dict[str, Any],
        token: str,
    ) -> httpx.Response:
        base = (profile.base_url or self._settings.gigachat_api_url).strip().rstrip("/")
        endpoint = (
            base
            if base.endswith("/chat/completions")
            else f"{base}/chat/completions"
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.gigachat_timeout_seconds,
                transport=self._transport,
                verify=self._verify,
            ) as client:
                return await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.TimeoutException as exc:
            raise GigaChatError("timeout", "GigaChat request timed out") from exc
        except httpx.HTTPError as exc:
            raise GigaChatError(
                "provider_unavailable", "GigaChat connection failed"
            ) from exc

    def _is_valid(self, token: GigaChatToken) -> bool:
        margin = timedelta(
            seconds=max(self._settings.gigachat_token_refresh_margin_seconds, 0)
        )
        return token.expires_at - margin > datetime.now(UTC)

    def _token_from_profile(self, profile: AIProviderProfile) -> GigaChatToken | None:
        if not profile.access_token or profile.oauth_expires_at is None:
            return None
        expires_at = profile.oauth_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return GigaChatToken(
            access_token=profile.access_token,
            expires_at=expires_at,
        )

    async def _persist_token(self, profile_id: int, token: GigaChatToken) -> None:
        if self._session_factory is None:
            return
        try:
            async with self._session_factory() as session:
                profile = await session.get(AIProviderProfile, profile_id)
                if profile is None:
                    return
                profile.access_token = token.access_token
                profile.oauth_expires_at = token.expires_at
                await session.commit()
        except Exception:
            logger.warning("gigachat_token_persist_failed", profile_id=profile_id)


def _parse_expires_at(body: dict[str, Any]) -> datetime:
    raw = body.get("expires_at")
    now = datetime.now(UTC)
    if isinstance(raw, int | float):
        value = float(raw)
        if value > 10_000_000_000:
            value /= 1000
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return now + timedelta(minutes=30)
    expires_in = body.get("expires_in")
    if isinstance(expires_in, int | float) and expires_in > 0:
        return now + timedelta(seconds=float(expires_in))
    return now + timedelta(minutes=30)


def _oauth_error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, str) and error:
            if error in {"invalid_client", "unsupported_scope"}:
                return error
            return f"http_{response.status_code}"
    return f"http_{response.status_code}"


__all__ = [
    "DEFAULT_API_URL",
    "DEFAULT_SCOPE",
    "GigaChatError",
    "GigaChatProvider",
    "GigaChatToken",
]
