"""CRUD and activation for AI provider profiles (S39-001)."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entities import AIProviderProfile


class AIProviderNotFoundError(Exception):
    """Requested profile does not exist."""


class AIProviderConflictError(Exception):
    """Profile name is already used."""


class AIProviderService:
    """Store OpenAI-compatible provider profiles in SQLite."""

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
        api_key: str | None = None,
    ) -> AIProviderProfile:
        async with self._session_factory() as session:
            has_any = await session.scalar(
                select(AIProviderProfile.id).limit(1)
            )
            profile = AIProviderProfile(
                name=name.strip(),
                base_url=base_url.strip(),
                model_name=model_name.strip(),
                api_key=(api_key or "").strip() or None,
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
        api_key: str | None = None,
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
            if api_key is not None and api_key.strip():
                profile.api_key = api_key.strip()
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise AIProviderConflictError(
                    f"provider name already exists: {name}"
                ) from exc
            await session.refresh(profile)
            return profile

    async def delete(self, profile_id: int) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(AIProviderProfile).where(AIProviderProfile.id == profile_id)
            )
            if result.rowcount == 0:
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
