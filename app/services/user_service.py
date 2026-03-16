from __future__ import annotations

from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.users import UserRepository
from app.services.permission_service import PermissionService


class UserService:
    def __init__(self, user_repo: UserRepository, permission: PermissionService) -> None:
        self._user_repo = user_repo
        self._permission = permission

    async def ensure_telegram_user(self, session: AsyncSession, tg_user: TgUser) -> User:
        user = await self._user_repo.get_or_create(
            session=session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            language_code=tg_user.language_code,
        )
        await self._permission.ensure_default_roles(session, user)
        return user

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        return await self._user_repo.get_by_telegram_id(session, telegram_id)

    async def ensure_system_user(self, session: AsyncSession, telegram_id: int, full_name: str | None = None) -> User:
        user = await self._user_repo.get_or_create(
            session=session,
            telegram_id=telegram_id,
            username=None,
            full_name=full_name or f"admin_{telegram_id}",
            language_code="ru",
        )
        await self._permission.ensure_default_roles(session, user)
        return user
