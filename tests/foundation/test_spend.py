from datetime import UTC, datetime
from decimal import Decimal

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.foundation.guardrails.spend import BudgetExhausted, NoSpendLimit, RedisSpendGuard, seconds_until_midnight


class FakeRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self.values: dict[str, float] = {}
        self.expiries: dict[str, int] = {}
        self.error = error

    async def get(self, key: str) -> str | None:
        if self.error is not None:
            raise self.error
        return str(self.values[key]) if key in self.values else None

    async def incrbyfloat(self, key: str, amount: float) -> float:
        if self.error is not None:
            raise self.error
        self.values[key] = self.values.get(key, 0.0) + amount
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds


def guard(client: FakeRedis, cap: float = 1.0) -> RedisSpendGuard:
    return RedisSpendGuard(client, cap_usd=cap)  # type: ignore[arg-type]


async def test_under_the_cap_the_call_is_allowed() -> None:
    spend = guard(FakeRedis(), cap=1.0)
    await spend.record(Decimal("0.40"))

    await spend.check()


async def test_at_the_cap_the_call_is_refused_until_midnight() -> None:
    spend = guard(FakeRedis(), cap=1.0)
    await spend.record(Decimal("0.60"))
    await spend.record(Decimal("0.40"))

    with pytest.raises(BudgetExhausted) as exhausted:
        await spend.check()

    assert 0 < exhausted.value.retry_after <= 24 * 3600


async def test_the_counter_belongs_to_one_day() -> None:
    client = FakeRedis()
    spend = guard(client)
    await spend.record(Decimal("0.10"))

    (key,) = client.values
    assert key == f"spend:{datetime.now(UTC):%Y-%m-%d}"
    # It outlives its day, so a clock skew around midnight cannot reset it early.
    assert client.expiries[key] > 24 * 3600


async def test_an_unknown_cost_is_not_counted_as_free_money() -> None:
    client = FakeRedis()

    await guard(client).record(None)

    assert client.values == {}


async def test_redis_being_down_lets_the_call_through() -> None:
    # A guard that turns an outage of an optional dependency into an outage of the product has
    # the priorities backwards.
    spend = guard(FakeRedis(error=RedisConnectionError("cache is down")))

    await spend.record(Decimal("5"))
    await spend.check()


async def test_spent_today_reports_what_was_recorded() -> None:
    spend = guard(FakeRedis())
    await spend.record(Decimal("0.25"))

    assert await spend.spent_today() == pytest.approx(0.25)


def test_seconds_until_midnight_counts_to_the_next_utc_day() -> None:
    assert seconds_until_midnight(datetime(2026, 9, 24, 23, 59, 0, tzinfo=UTC)) == 60


async def test_without_redis_nothing_is_capped() -> None:
    await NoSpendLimit().record(Decimal("100"))
    await NoSpendLimit().check()
