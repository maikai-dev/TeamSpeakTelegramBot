from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.db.repositories.users import UserRepository
from app.db.session import create_engine, create_session_factory
from app.services.permission_service import PermissionService
from app.services.user_service import UserService


async def run(admin_ids: list[int]) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    user_repo = UserRepository()
    permission = PermissionService(settings=settings, user_repo=user_repo)
    users = UserService(user_repo=user_repo, permission=permission)

    async with session_factory() as session:
        await permission.ensure_roles_seeded(session)
        for tg_id in admin_ids:
            user = await users.ensure_system_user(session, tg_id, full_name=f"bootstrap_admin_{tg_id}")
            await permission.promote_admin(session, user.id)
        await session.commit()

    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Telegram admin users")
    parser.add_argument("--admin-id", action="append", type=int, default=[], help="Telegram ID администратора")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    settings = get_settings()
    ids = args.admin_id or settings.bootstrap_admin_tg_ids or settings.bot_admin_ids
    if not ids:
        raise SystemExit("Не передан admin id. Используйте --admin-id или BOOTSTRAP_ADMIN_TG_IDS")
    asyncio.run(run(ids))
    print(f"Bootstrap завершен. Добавлено admin: {ids}")
