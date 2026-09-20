"""Exact-match cache: the cheapest review is the one we do not ask for.

The key is a SHA-256 of the **full** prompts plus the generation knobs, not of the listing
text. That matters: editing the checklist, bumping the prompt version or switching the model
changes the key on its own, so a stale review cannot survive a change that would have altered
it. No manual flushing, no "did I remember to clear the cache?".

The cache is an optimisation, never a dependency: if Redis is down, the review is computed as
usual and the failure is logged.
"""

import hashlib
from typing import Protocol

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.schemas.listing_review import ListingReview

log = structlog.get_logger()

DEFAULT_TTL_SECONDS = 86_400


def make_key(*, system: str, user: str, model: str, prompt_version: str) -> str:
    fingerprint = "\n".join([prompt_version, model, system, user])
    return f"review:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()}"


class ReviewStore(Protocol):
    """What the conductor needs from a cache: look up, and remember."""

    async def get(self, key: str) -> ListingReview | None: ...

    async def set(self, key: str, review: ListingReview) -> None: ...


class ReviewCache:
    def __init__(self, client: Redis, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> "ReviewCache":
        return cls(Redis.from_url(url, decode_responses=True), ttl_seconds=ttl_seconds)

    async def get(self, key: str) -> ListingReview | None:
        try:
            cached = await self._client.get(key)
        except RedisError:
            log.warning("cache.unavailable", operation="get", exc_info=True)
            return None
        if cached is None:
            return None
        return ListingReview.model_validate_json(cached)

    async def set(self, key: str, review: ListingReview) -> None:
        try:
            await self._client.set(key, review.model_dump_json(), ex=self._ttl)
        except RedisError:
            log.warning("cache.unavailable", operation="set", exc_info=True)


class NullCache:
    """Used when no Redis is configured: every review is computed."""

    async def get(self, key: str) -> ListingReview | None:
        return None

    async def set(self, key: str, review: ListingReview) -> None:
        return None
