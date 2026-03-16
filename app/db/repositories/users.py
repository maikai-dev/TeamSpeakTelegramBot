from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RoleName
from app.db.models import Role, User, UserRole


class UserRepository:
    async def ensure_roles_seeded(self, session: AsyncSession) -> None:
        existing = {
            role.name
            for role in (await session.execute(select(Role))).scalars().all()
        }
        missing = [
            Role(name=role_name, description=f"Системная роль {role_name.value}")
            for role_name in RoleName
            if role_name not in existing
        ]
        if missing:
            session.add_all(missing)
            await session.flush()

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
        language_code: str | None,
    ) -> User:
        user = await self.get_by_telegram_id(session, telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                language_code=language_code,
                is_active=True,
            )
            session.add(user)
            await session.flush()
        else:
            user.username = username
            user.full_name = full_name
            user.language_code = language_code
            user.last_seen_at = datetime.utcnow()
        return user

    async def assign_role(
        self,
        session: AsyncSession,
        user_id: int,
        role_name: RoleName,
        assigned_by_user_id: int | None = None,
    ) -> None:
        role = (
            await session.execute(select(Role).where(Role.name == role_name))
        ).scalar_one()
        exists_stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        exists = (await session.execute(exists_stmt)).scalar_one_or_none()
        if exists:
            return
        session.add(
            UserRole(
                user_id=user_id,
                role_id=role.id,
                assigned_by_user_id=assigned_by_user_id,
            )
        )

    async def remove_role(self, session: AsyncSession, user_id: int, role_name: RoleName) -> None:
        role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
        if not role:
            return
        await session.execute(
            delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        )

    async def has_role(self, session: AsyncSession, user_id: int, role_name: RoleName) -> bool:
        stmt = (
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, Role.name == role_name)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def list_admin_telegram_ids(self, session: AsyncSession) -> list[int]:
        stmt = (
            select(User.telegram_id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == RoleName.ADMIN)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(self, session: AsyncSession, user_ids: Sequence[int]) -> list[User]:
        if not user_ids:
            return []
        stmt = select(User).where(User.id.in_(user_ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())
