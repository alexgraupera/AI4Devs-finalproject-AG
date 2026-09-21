"""A fixed window over Redis, so the corpus is not a free API for whoever finds the URL.

Every query costs an embedding call and every answer costs two model calls. Without a limit,
one loop empties the API budget in minutes, and the spend limit at the provider is a blunter
instrument than this one.

**The limiter never takes the service down.** If Redis is unreachable the request is allowed and
the failure is logged: a rate limiter that turns an outage of an optional dependency into an
outage of the product has the priorities backwards.

Fixed window, not sliding: it admits a burst at a window boundary, which for a budget guard is
an acceptable imprecision and one fewer moving part.
"""

import time
from typing import Protocol

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = structlog.get_logger()

DEFAULT_REQUESTS = 30
DEFAULT_WINDOW_SECONDS = 60


class RateLimited(Exception):
    """The caller has spent its allowance for this window."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class RateLimiter(Protocol):
    async def check(self, identity: str) -> None: ...


class RedisRateLimiter:
    def __init__(
        self,
        client: Redis,
        *,
        requests: int = DEFAULT_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self._requests = requests
        self._window = window_seconds

    @classmethod
    def from_url(cls, url: str, *, requests: int, window_seconds: int) -> "RedisRateLimiter":
        return cls(Redis.from_url(url, decode_responses=True), requests=requests, window_seconds=window_seconds)

    async def check(self, identity: str) -> None:
        window_start = int(time.time()) // self._window
        key = f"ratelimit:{identity}:{window_start}"

        try:
            count = await self._client.incr(key)
            if count == 1:
                # Only the first request of a window sets the expiry: the window is fixed, not
                # extended by traffic, or a busy caller would never be let back in.
                await self._client.expire(key, self._window)
        except RedisError:
            log.warning("rate_limit.unavailable", exc_info=True)
            return

        if count > self._requests:
            retry_after = self._window - int(time.time()) % self._window
            log.info("rate_limit.exceeded", identity=identity, count=count, limit=self._requests)
            raise RateLimited(retry_after=retry_after)


class NoRateLimit:
    """Used when no Redis is configured: local development is not rate limited."""

    async def check(self, identity: str) -> None:
        return None
