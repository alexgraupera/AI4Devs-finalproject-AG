"""Composition root: every singleton is built here, and only here.

It lives above the layers on purpose: wiring is its job, so it is allowed to reach into any
of them. Routers and tests import it; nothing else does.
"""

from functools import lru_cache

from app.config import get_settings
from app.domain.listing_review_service import ListingReviewService
from app.foundation.llm.wrapper import LLMWrapper


@lru_cache
def get_llm_wrapper() -> LLMWrapper:
    settings = get_settings()
    return LLMWrapper(model=settings.llm_model, max_retries=settings.llm_max_retries)


@lru_cache
def get_listing_review_service() -> ListingReviewService:
    return ListingReviewService(llm=get_llm_wrapper())
