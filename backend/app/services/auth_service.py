"""Single-user authentication service (v1.0.0, Sprint 47)."""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models.entities import User

logger = structlog.get_logger(__name__)

JWT_ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12


class AuthService:
    """Password hashing, JWT issue/verify and bootstrap for one user."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._secret = settings.auth_jwt_secret or secrets.token_urlsafe(48)
        if not settings.auth_jwt_secret:
            logger.warning(
                "auth_jwt_secret_generated",
                message="AUTH_JWT_SECRET is empty; using an ephemeral secret",
            )
        self._attempts: dict[str, list[float]] = {}

    async def bootstrap_admin(self) -> bool:
        """Create the default admin if the users table is empty."""
        async with self._session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(User))
            if count:
                return False
            user = User(
                username=self._settings.admin_username.strip() or "admin",
                hashed_password=self.hash_password(
                    self._settings.admin_password or "admin"
                ),
                is_active=True,
                role="admin",
            )
            session.add(user)
            await session.commit()
        logger.info(
            "default_admin_user_created",
            message="Default admin user created.",
            username=self._settings.admin_username,
        )
        return True

    async def get_by_username(self, username: str) -> User | None:
        async with self._session_factory() as session:
            user = await session.scalar(
                select(User).where(User.username == username.strip())
            )
        return user if isinstance(user, User) else None

    async def get_by_id(self, user_id: int) -> User | None:
        async with self._session_factory() as session:
            return await session.get(User, user_id)

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.get_by_username(username)
        if user is None or not user.is_active:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        async with self._session_factory() as session:
            stored = await session.get(User, user.id)
            if stored is not None:
                stored.last_login_at = datetime.now(UTC)
                await session.commit()
        return user

    async def create_user(
        self,
        username: str,
        password: str,
        *,
        role: str = "auditor",
        is_active: bool = True,
    ) -> User:
        async with self._session_factory() as session:
            user = User(
                username=username.strip(),
                hashed_password=self.hash_password(password),
                is_active=is_active,
                role=role,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def list_users(self) -> list[User]:
        async with self._session_factory() as session:
            rows = await session.scalars(select(User).order_by(User.id))
            return list(rows.all())

    async def update_user(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> User | None:
        """Update a user after the API-level lockout checks."""
        async with self._session_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                return None
            if role is not None:
                user.role = role
            if is_active is not None:
                user.is_active = is_active
            if password:
                user.hashed_password = self.hash_password(password)
            await session.commit()
            await session.refresh(user)
            return user

    async def count_admins(self) -> int:
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == "admin", User.is_active.is_(True))
            )
            return int(count or 0)

    def create_access_token(self, user: User) -> tuple[str, datetime]:
        now = datetime.now(UTC)
        expires_at = now + timedelta(
            seconds=max(int(self._settings.auth_token_ttl_seconds), 60)
        )
        payload = {
            "sub": str(user.id),
            "role": user.role,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": secrets.token_hex(8),
        }
        token = jwt.encode(payload, self._secret, algorithm=JWT_ALGORITHM)
        return token, expires_at

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.PyJWTError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    async def user_from_token(self, token: str) -> User | None:
        payload = self.decode_token(token)
        if payload is None:
            return None
        raw_id = payload.get("sub")
        if not isinstance(raw_id, str | int):
            return None
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            return None
        user = await self.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user

    def allow_login(self, key: str) -> bool:
        now = time.monotonic()
        window = max(int(self._settings.auth_login_rate_window_seconds), 1)
        limit = max(int(self._settings.auth_login_rate_limit), 1)
        attempts = [
            stamp
            for stamp in self._attempts.get(key, [])
            if now - stamp < window
        ]
        self._attempts[key] = attempts
        return len(attempts) < limit

    def record_login_failure(self, key: str) -> None:
        self._attempts.setdefault(key, []).append(time.monotonic())

    def clear_login_failures(self, key: str) -> None:
        self._attempts.pop(key, None)

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
        ).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hashed.encode("utf-8"),
            )
        except ValueError:
            return False


__all__ = ["BCRYPT_ROUNDS", "JWT_ALGORITHM", "AuthService"]
