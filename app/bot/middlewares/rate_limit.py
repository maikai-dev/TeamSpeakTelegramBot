from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.core.config import Settings
from app.services.container import ServiceContainer


class GlobalRateLimitMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[object]],
        event: TelegramObject,
        data: dict,
    ) -> object:
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        if not event.text.startswith("/"):
            return await handler(event, data)

        services: ServiceContainer = data["services"]
        key = f"global:{event.from_user.id if event.from_user else 0}"
        allowed = await services.rate_limiter.check(
            key=key,
            limit=self._settings.bot_rate_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            await event.answer("Слишком много команд. Подождите немного.")
            return None

        return await handler(event, data)
