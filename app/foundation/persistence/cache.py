"""Whether the Redis behind the cache, the rate limiter and the spend guard answers.

Reported by the readiness probe and nothing more: all three fail open, so Redis being down makes
the service slower and uncapped, not unavailable.
"""

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.foundation.persistence.database import DISABLED, OK, UNAVAILABLE

log = structlog.get_logger()


async def cache_status(client: Redis | None) -> str:
    """`disabled` (not configured), `unavailable` (configured but not answering) or `ok`."""
    if client is None:
        return DISABLED
    try:
        await client.ping()
    except (RedisError, OSError):
        log.warning("cache.unavailable", operation="ping", exc_info=True)
        return UNAVAILABLE
    return OK
