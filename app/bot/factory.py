from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers import get_routers
from app.bot.middlewares import DBSessionMiddleware, GlobalRateLimitMiddleware, UserContextMiddleware
from app.core.config import Settings
from app.services.container import ServiceContainer


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    settings: Settings,
    services: ServiceContainer,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
) -> Dispatcher:
    storage = RedisStorage(redis) if redis else MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp["services"] = services
    dp["settings"] = settings

    dp.update.middleware(DBSessionMiddleware(session_factory))
    dp.update.middleware(UserContextMiddleware())
    dp.update.middleware(GlobalRateLimitMiddleware(settings))

    for router in get_routers():
        dp.include_router(router)

    return dp
