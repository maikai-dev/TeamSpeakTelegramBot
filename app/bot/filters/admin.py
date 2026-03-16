from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.db.models import User
from app.services.container import ServiceContainer


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message, services: ServiceContainer, user: User, session) -> bool:
        return await services.permission.is_admin(session, user)
