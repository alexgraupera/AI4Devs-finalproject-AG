"""A daily cap on what the models may cost, enforced before the call instead of reported after it.

The rate limiter bounds how often one caller may ask. It does not bound what all callers together
spend: thirty requests a minute from a handful of keys, or one runaway loop, drain a budget just as
well. The production session calls it denial of wallet, and the provider's own spend limit is the
last line, not the first: when it trips, every feature stops at once and nobody chose which.

So the service keeps its own counter of what it spent today (UTC), checks it before asking a model
and adds the real cost afterwards. At the cap it stops calling models until midnight and says so,
rather than raising an alert nobody may be reading.

**The guard never takes the service down.** If Redis is unreachable the call is allowed and the
failure logged, as the rate limiter does: an optional dependency failing must not become an outage.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = structlog.get_logger()

DEFAULT_CAP_USD = 2.0
# Kept a day longer than the day it counts, so a clock skew around midnight cannot reset it early.
_KEY_TTL_SECONDS = 2 * 24 * 3600


class BudgetExhausted(Exception):
    """Today's spend reached the cap: no model call until the day turns."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"daily spend cap reached, retry after {retry_after}s")
        self.retry_after = retry_after


class SpendGuard(Protocol):
    async def check(self) -> None: ...

    async def record(self, cost_usd: Decimal | None) -> None: ...


def seconds_until_midnight(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


class RedisSpendGuard:
    def __init__(self, client: Redis, *, cap_usd: float = DEFAULT_CAP_USD) -> None:
        self._client = client
        self._cap = cap_usd

    async def check(self) -> None:
        now = datetime.now(UTC)
        try:
            spent = await self._client.get(self._key(now))
        except RedisError:
            log.warning("spend.unavailable", operation="check", exc_info=True)
            return

        if spent is not None and float(spent) >= self._cap:
            log.warning("spend.cap_reached", spent_usd=float(spent), cap_usd=self._cap)
            raise BudgetExhausted(retry_after=seconds_until_midnight(now))

    async def record(self, cost_usd: Decimal | None) -> None:
        if cost_usd is None:
            # A model missing from the price table has no known cost. Counting it as zero would
            # let an unpriced model spend without limit, so it is at least made visible.
            log.warning("spend.unknown_cost")
            return
        if cost_usd <= 0:
            return

        key = self._key(datetime.now(UTC))
        try:
            await self._client.incrbyfloat(key, float(cost_usd))
            await self._client.expire(key, _KEY_TTL_SECONDS)
        except RedisError:
            log.warning("spend.unavailable", operation="record", exc_info=True)

    async def spent_today(self) -> float | None:
        """What today cost so far, or None when it cannot be known. For the readiness probe."""
        try:
            spent = await self._client.get(self._key(datetime.now(UTC)))
        except RedisError:
            return None
        return float(spent) if spent is not None else 0.0

    @property
    def cap_usd(self) -> float:
        return self._cap

    @staticmethod
    def _key(now: datetime) -> str:
        return f"spend:{now:%Y-%m-%d}"


class NoSpendLimit:
    """Used when no Redis is configured: local development spends without a cap."""

    async def check(self) -> None:
        return None

    async def record(self, cost_usd: Decimal | None) -> None:
        return None
