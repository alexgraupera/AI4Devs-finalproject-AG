from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    ListingReview,
    Severity,
    Verdict,
)
from app.generation.cag.exact import NullCache, ReviewCache, make_key

A_KEY = {"system": "system prompt", "user": "user prompt", "model": "claude-haiku-4-5", "prompt_version": "v2"}


class FakeRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self.values: dict[str, str] = {}
        self.error = error
        self.expirations: list[int | None] = []

    async def get(self, key: str) -> str | None:
        if self.error is not None:
            raise self.error
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.error is not None:
            raise self.error
        self.values[key] = value
        self.expirations.append(ex)


def a_review() -> ListingReview:
    return ListingReview(
        findings=[
            Finding(
                category=FindingCategory.DEPOSIT_AND_GUARANTEES,
                severity=Severity.HIGH,
                message="La fianza supera una mensualidad",
                suggestion="Ajusta la fianza",
                legal_basis="LAU art. 36.1",
            )
        ],
        verdict=Verdict.REQUEST_CHANGES,
        summary="Hay que corregir la fianza",
    )


def cache_with(client: Any, ttl_seconds: int = 60) -> ReviewCache:
    return ReviewCache(client, ttl_seconds=ttl_seconds)


def test_the_same_call_produces_the_same_key() -> None:
    assert make_key(**A_KEY) == make_key(**A_KEY)


@pytest.mark.parametrize("field", ["system", "user", "model", "prompt_version"])
def test_any_change_produces_a_different_key(field: str) -> None:
    changed = A_KEY | {field: "something else"}

    assert make_key(**changed) != make_key(**A_KEY)


async def test_returns_nothing_on_a_miss() -> None:
    assert await cache_with(FakeRedis()).get(make_key(**A_KEY)) is None


async def test_returns_the_stored_review_on_a_hit() -> None:
    cache = cache_with(FakeRedis())
    key = make_key(**A_KEY)

    await cache.set(key, a_review())

    assert await cache.get(key) == a_review()


async def test_stores_the_review_with_the_configured_ttl() -> None:
    client = FakeRedis()

    await cache_with(client, ttl_seconds=120).set(make_key(**A_KEY), a_review())

    assert client.expirations == [120]


async def test_treats_a_redis_failure_as_a_miss() -> None:
    cache = cache_with(FakeRedis(error=RedisConnectionError("cache is down")))

    assert await cache.get(make_key(**A_KEY)) is None


async def test_a_redis_failure_while_storing_does_not_break_the_review() -> None:
    cache = cache_with(FakeRedis(error=RedisConnectionError("cache is down")))

    await cache.set(make_key(**A_KEY), a_review())


async def test_the_null_cache_never_answers() -> None:
    cache = NullCache()
    key = make_key(**A_KEY)

    await cache.set(key, a_review())

    assert await cache.get(key) is None
