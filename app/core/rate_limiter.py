from __future__ import annotations

import asyncio
import time

from redis.asyncio import Redis


class RateLimiter:
    """Простой токен-лимитер через Redis c fallback in-memory."""

    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis
        self._fallback: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return True

        if self._redis:
            redis_key = f"rl:{key}:{window_seconds}"
            current = await self._redis.incr(redis_key)
            if current == 1:
                await self._redis.expire(redis_key, window_seconds)
            return int(current) <= limit

        async with self._lock:
            now = time.monotonic()
            count, expires_at = self._fallback.get(key, (0, now + window_seconds))
            if now > expires_at:
                count = 0
                expires_at = now + window_seconds
            count += 1
            self._fallback[key] = (count, expires_at)
            return count <= limit
