from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.enums import RoleName
from app.db.repositories.users import UserRepository
from app.services.permission_service import PermissionService


def build_settings(admin_ids: str = "") -> Settings:
    return Settings(
        BOT_TOKEN="token",
        BOT_ADMIN_IDS=admin_ids,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        REDIS_URL="redis://localhost:6379/0",
        TS3_HOST="127.0.0.1",
        TS3_QUERY_LOGIN="serveradmin",
        TS3_QUERY_PASSWORD="pass",
    )


@pytest.mark.asyncio
async def test_permission_assigns_user_role(session) -> None:
    repo = UserRepository()
    settings = build_settings(admin_ids="")
    service = PermissionService(settings=settings, user_repo=repo)

    await repo.ensure_roles_seeded(session)
    user = await repo.get_or_create(
        session=session,
        telegram_id=111,
        username="user",
        full_name="User",
        language_code="ru",
    )
    await service.ensure_default_roles(session, user)
    await session.commit()

    assert await repo.has_role(session, user.id, RoleName.USER) is True
    assert await repo.has_role(session, user.id, RoleName.ADMIN) is False


@pytest.mark.asyncio
async def test_permission_assigns_admin_from_settings(session) -> None:
    repo = UserRepository()
    settings = build_settings(admin_ids="222")
    service = PermissionService(settings=settings, user_repo=repo)

    await repo.ensure_roles_seeded(session)
    user = await repo.get_or_create(
        session=session,
        telegram_id=222,
        username="boss",
        full_name="Boss",
        language_code="ru",
    )
    await service.ensure_default_roles(session, user)
    await session.commit()

    assert await service.is_admin(session, user) is True
