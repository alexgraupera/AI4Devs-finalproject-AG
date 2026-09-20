"""The conductor: the only place where the pieces of a review are wired together.

Today it renders the prompts and calls the LLM. Guardrails, caches and retrieval are added
as steps here, never inside the layers themselves, so the pipeline stays readable as it grows.
"""

from app.domain.schemas.listing_review import Listing, ListingReview
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_listing_review_prompt

PROMPT_VERSION = "v1"


class ListingReviewService:
    def __init__(self, llm: StructuredLLM, prompt_version: str = PROMPT_VERSION) -> None:
        self._llm = llm
        self._prompt_version = prompt_version

    async def review(self, listing: Listing) -> ListingReview:
        system, user = render_listing_review_prompt(listing, version=self._prompt_version)
        return await self._llm.complete_structured(system=system, user=user, schema=ListingReview)
