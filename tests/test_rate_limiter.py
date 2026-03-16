from __future__ import annotations

import pytest

from app.core.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_inmemory_rate_limiter_allows_then_blocks() -> None:
    limiter = RateLimiter(redis=None)

    assert await limiter.check("k", limit=2, window_seconds=60) is True
    assert await limiter.check("k", limit=2, window_seconds=60) is True
    assert await limiter.check("k", limit=2, window_seconds=60) is False
