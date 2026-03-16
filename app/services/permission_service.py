from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import RoleName
from app.db.models import User
from app.db.repositories.users import UserRepository


class PermissionService:
    def __init__(self, settings: Settings, user_repo: UserRepository) -> None:
        self._settings = settings
        self._user_repo = user_repo

    async def ensure_default_roles(self, session: AsyncSession, user: User) -> None:
        await self._user_repo.ensure_roles_seeded(session)
        await self._user_repo.assign_role(session, user.id, RoleName.USER)
        if user.telegram_id in self._settings.bot_admin_ids:
            await self._user_repo.assign_role(session, user.id, RoleName.ADMIN)

    async def ensure_roles_seeded(self, session: AsyncSession) -> None:
        await self._user_repo.ensure_roles_seeded(session)

    async def promote_admin(self, session: AsyncSession, user_id: int) -> None:
        await self._user_repo.assign_role(session, user_id, RoleName.ADMIN)
        await self._user_repo.assign_role(session, user_id, RoleName.USER)

    async def is_admin(self, session: AsyncSession, user: User) -> bool:
        if user.telegram_id in self._settings.bot_admin_ids:
            return True
        return await self._user_repo.has_role(session, user.id, RoleName.ADMIN)

    async def is_user(self, session: AsyncSession, user: User) -> bool:
        return await self._user_repo.has_role(session, user.id, RoleName.USER)
