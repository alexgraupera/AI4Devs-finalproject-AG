"""The conductor: the only place where the pieces of a review are wired together.

Order matters and is the point of this class: guardrails reject before we spend a token, the
cache answers before the model is asked, the prompts are rendered from a pinned version, and
the output guardrail has the last word before anything reaches the user.

The cache and the model never meet each other: they meet here.
"""

import time
from decimal import Decimal

import structlog

from app.domain.errors import NotAListing
from app.domain.schemas.listing_review import Listing, ListingReview, ReviewCandidate, ReviewedListing
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import check_review
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_listing_review_prompt
from app.generation.cag.exact import ReviewStore, make_key

log = structlog.get_logger()

PROMPT_VERSION = "v2"


class ListingReviewService:
    def __init__(
        self,
        llm: StructuredLLM,
        moderation: ModerationClient | None = None,
        cache: ReviewStore | None = None,
        model: str = "",
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._llm = llm
        self._moderation = moderation
        self._cache = cache
        self._model = model
        self._prompt_version = prompt_version

    async def review(self, listing: Listing) -> ReviewedListing:
        await check_input(listing.text, moderation=self._moderation)

        system, user = render_listing_review_prompt(listing, version=self._prompt_version)

        cached = await self._from_cache(system=system, user=user)
        if cached is not None:
            return cached

        completion = await self._llm.complete_structured(system=system, user=user, schema=ReviewCandidate)
        usage = completion.usage

        log.info(
            "listing_review.completed",
            prompt_version=self._prompt_version,
            provider=usage.provider,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
            estimated_cost_usd=float(usage.estimated_cost_usd) if usage.estimated_cost_usd is not None else None,
            attempts=usage.attempts,
            is_rental_listing=completion.output.is_rental_listing,
        )

        if not completion.output.is_rental_listing:
            # Not cached on purpose: a "this is not a listing" answer is cheap to recompute and
            # the text is unlikely to be sent twice.
            raise NotAListing(completion.output.summary)

        review = check_review(completion.output.to_review())
        await self._store(system=system, user=user, review=review)

        return ReviewedListing(review=review, usage=usage, cached=False)

    async def _from_cache(self, *, system: str, user: str) -> ReviewedListing | None:
        if self._cache is None:
            return None

        started = time.perf_counter()
        key = self._key(system=system, user=user)
        review = await self._cache.get(key)
        latency_ms = int((time.perf_counter() - started) * 1000)

        if review is None:
            log.info("listing_review.cache_miss", prompt_version=self._prompt_version, model=self._model)
            return None

        log.info(
            "listing_review.cache_hit",
            prompt_version=self._prompt_version,
            model=self._model,
            latency_ms=latency_ms,
        )
        return ReviewedListing(review=review, usage=self._cache_usage(latency_ms), cached=True)

    async def _store(self, *, system: str, user: str, review: ListingReview) -> None:
        if self._cache is None:
            return
        await self._cache.set(self._key(system=system, user=user), review)

    def _key(self, *, system: str, user: str) -> str:
        return make_key(system=system, user=user, model=self._model, prompt_version=self._prompt_version)

    def _cache_usage(self, latency_ms: int) -> LLMUsage:
        """A cache hit spends no tokens, and says so instead of reporting the original cost."""
        return LLMUsage(
            provider="cache",
            model=self._model,
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
            estimated_cost_usd=Decimal(0),
            attempts=0,
        )
