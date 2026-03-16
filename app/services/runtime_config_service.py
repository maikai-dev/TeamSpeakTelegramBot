from __future__ import annotations

from redis.asyncio import Redis


class RuntimeConfigService:
    def __init__(self, redis: Redis | None, chatwatch_default: bool) -> None:
        self._redis = redis
        self._chatwatch_default = chatwatch_default
        self._fallback_chatwatch = chatwatch_default

    async def is_chatwatch_enabled(self) -> bool:
        if self._redis:
            value = await self._redis.get("feature:chatwatch_enabled")
            if value is None:
                return self._chatwatch_default
            return value.decode("utf-8") == "1"
        return self._fallback_chatwatch

    async def set_chatwatch_enabled(self, enabled: bool) -> None:
        if self._redis:
            await self._redis.set("feature:chatwatch_enabled", "1" if enabled else "0")
        self._fallback_chatwatch = enabled

    async def toggle_chatwatch(self) -> bool:
        current = await self.is_chatwatch_enabled()
        new_state = not current
        await self.set_chatwatch_enabled(new_state)
        return new_state

    async def ping(self) -> bool:
        if not self._redis:
            return True
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
