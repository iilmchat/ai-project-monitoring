"""CRUD and activation for AI provider profiles (S39-001, S43-002)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entities import AIProviderProfile


class AIProviderNotFoundError(Exception):
    """Requested profile does not exist."""


class AIProviderConflictError(Exception):
    """Profile name is already used."""


class AIProviderService:
    """Store AI provider profiles (OpenAI-compatible and GigaChat) in SQLite."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_profiles(self) -> list[AIProviderProfile]:
        async with self._session_factory() as session:
            return list(
                (
                    await session.scalars(
                        select(AIProviderProfile).order_by(
                            AIProviderProfile.is_active.desc(),
                            AIProviderProfile.id,
                        )
                    )
                ).all()
            )

    async def get(self, profile_id: int) -> AIProviderProfile:
        async with self._session_factory() as session:
            profile = await session.get(AIProviderProfile, profile_id)
        if profile is None:
            raise AIProviderNotFoundError(f"provider {profile_id} not found")
        return profile

    async def get_active(self) -> AIProviderProfile | None:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(AIProviderProfile)
                .where(AIProviderProfile.is_active.is_(True))
                .order_by(AIProviderProfile.id)
                .limit(1)
            )
            return result.first()

    async def create(
        self,
        *,
        name: str,
        base_url: str,
        model_name: str,
        embedding_model: str | None = None,
        api_key: str | None = None,
        provider_type: str = "openai_compatible",
        auth_type: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        oauth_scope: str | None = None,
        oauth_expires_at: datetime | None = None,
        access_token: str | None = None,
    ) -> AIProviderProfile:
        async with self._session_factory() as session:
            has_any = await session.scalar(
                select(AIProviderProfile.id).limit(1)
            )
            profile = AIProviderProfile(
                name=name.strip(),
                base_url=base_url.strip(),
                model_name=model_name.strip(),
                embedding_model=(embedding_model or "").strip() or None,
                api_key=(api_key or "").strip() or None,
                provider_type=provider_type,
                auth_type=(
                    "oauth"
                    if provider_type == "gigachat"
                    else (auth_type or "api_key")
                ),
                client_id=(client_id or "").strip() or None,
                client_secret=(client_secret or "").strip() or None,
                oauth_scope=oauth_scope,
                oauth_expires_at=oauth_expires_at,
                access_token=access_token,
                is_active=has_any is None,
            )
            session.add(profile)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AIProviderConflictError(
                    f"provider name already exists: {name}"
                ) from exc
            await session.refresh(profile)
            return profile

    async def update(
        self,
        profile_id: int,
        *,
        name: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        embedding_model: str | None = None,
        api_key: str | None = None,
        provider_type: str | None = None,
        auth_type: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        oauth_scope: str | None = None,
    ) -> AIProviderProfile:
        async with self._session_factory() as session:
            profile = await session.get(AIProviderProfile, profile_id)
            if profile is None:
                raise AIProviderNotFoundError(
                    f"provider {profile_id} not found"
                )
            if name is not None and name.strip():
                profile.name = name.strip()
            if base_url is not None and base_url.strip():
                profile.base_url = base_url.strip()
            if model_name is not None and model_name.strip():
                profile.model_name = model_name.strip()
            if embedding_model is not None:
                profile.embedding_model = embedding_model.strip() or None
            if api_key is not None and api_key.strip():
                profile.api_key = api_key.strip()
            if provider_type is not None:
                profile.provider_type = provider_type
                if provider_type == "gigachat":
                    profile.auth_type = "oauth"
            if auth_type is not None:
                profile.auth_type = auth_type
            if client_id is not None and client_id.strip():
                profile.client_id = client_id.strip()
            if client_secret is not None and client_secret.strip():
                profile.client_secret = client_secret.strip()
            if oauth_scope is not None:
                profile.oauth_scope = oauth_scope
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AIProviderConflictError(
                    f"provider name already exists: {name}"
                ) from exc
            await session.refresh(profile)
            return profile

    async def upsert_gigachat(
        self,
        *,
        name: str,
        base_url: str,
        model_name: str,
        client_id: str,
        client_secret: str,
        scope: str,
        expires_at: datetime,
        access_token: str,
        activate: bool,
    ) -> AIProviderProfile:
        """Create or re-authorise a GigaChat profile without duplicating it."""
        async with self._session_factory() as session:
            profile = await session.scalar(
                select(AIProviderProfile).where(
                    AIProviderProfile.name == name.strip()
                )
            )
            if profile is None:
                has_any = await session.scalar(
                    select(AIProviderProfile.id).limit(1)
                )
                profile = AIProviderProfile(
                    name=name.strip(),
                    base_url=base_url.strip(),
                    model_name=model_name.strip(),
                    api_key=None,
                    provider_type="gigachat",
                    auth_type="oauth",
                    client_id=client_id.strip(),
                    client_secret=client_secret.strip(),
                    oauth_scope=scope,
                    oauth_expires_at=expires_at,
                    access_token=access_token,
                    is_active=has_any is None or activate,
                )
                session.add(profile)
            else:
                profile.provider_type = "gigachat"
                profile.auth_type = "oauth"
                profile.base_url = base_url.strip()
                profile.model_name = model_name.strip()
                profile.client_id = client_id.strip()
                profile.client_secret = client_secret.strip()
                profile.oauth_scope = scope
                profile.oauth_expires_at = expires_at
                profile.access_token = access_token
                if activate:
                    profile.is_active = True
            if activate:
                await session.flush()
                await session.execute(
                    update(AIProviderProfile)
                    .where(AIProviderProfile.id != profile.id)
                    .values(is_active=False)
                )
            await session.commit()
            await session.refresh(profile)
            return profile

    async def delete(self, profile_id: int) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(AIProviderProfile).where(AIProviderProfile.id == profile_id)
            )
            if getattr(result, "rowcount", 0) == 0:
                raise AIProviderNotFoundError(
                    f"provider {profile_id} not found"
                )
            await session.commit()

    async def activate(self, profile_id: int) -> AIProviderProfile:
        async with self._session_factory() as session:
            profile = await session.get(AIProviderProfile, profile_id)
            if profile is None:
                raise AIProviderNotFoundError(
                    f"provider {profile_id} not found"
                )
            await session.execute(
                update(AIProviderProfile).values(is_active=False)
            )
            profile.is_active = True
            await session.commit()
            await session.refresh(profile)
            return profile


__all__ = [
    "AIProviderConflictError",
    "AIProviderNotFoundError",
    "AIProviderService",
]
