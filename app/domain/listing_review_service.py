"""The conductor: the only place where the pieces of a review are wired together.

Order matters and is the point of this class: guardrails reject before we spend a token,
the prompts are rendered from a pinned version, the model answers into a schema, and the
output guardrail has the last word before anything reaches the user.
"""

from app.domain.errors import NotAListing
from app.domain.schemas.listing_review import Listing, ListingReview, ReviewCandidate
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import check_review
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_listing_review_prompt

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

    async def review(self, listing: Listing) -> ListingReview:
        await check_input(listing.text, moderation=self._moderation)

        system, user = render_listing_review_prompt(listing, version=self._prompt_version)
        candidate = await self._llm.complete_structured(system=system, user=user, schema=ReviewCandidate)

        if not candidate.is_rental_listing:
            raise NotAListing(candidate.summary)

        return check_review(candidate.to_review())
