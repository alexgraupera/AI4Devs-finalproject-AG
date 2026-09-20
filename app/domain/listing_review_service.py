"""The conductor: the only place where the pieces of a review are wired together.

Order matters and is the point of this class: guardrails reject before we spend a token,
the prompts are rendered from a pinned version, the model answers into a schema, and the
output guardrail has the last word before anything reaches the user.
"""

import structlog

from app.domain.errors import NotAListing
from app.domain.schemas.listing_review import Listing, ReviewCandidate, ReviewedListing
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import check_review
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_listing_review_prompt

log = structlog.get_logger()

PROMPT_VERSION = "v2"


class ListingReviewService:
    def __init__(
        self,
        llm: StructuredLLM,
        moderation: ModerationClient | None = None,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._llm = llm
        self._moderation = moderation
        self._prompt_version = prompt_version

    async def review(self, listing: Listing) -> ReviewedListing:
        await check_input(listing.text, moderation=self._moderation)

        system, user = render_listing_review_prompt(listing, version=self._prompt_version)
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
            is_rental_listing=completion.output.is_rental_listing,
        )

        if not completion.output.is_rental_listing:
            raise NotAListing(completion.output.summary)

        return ReviewedListing(review=check_review(completion.output.to_review()), usage=usage)
