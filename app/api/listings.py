"""Transport for the listing review. No business logic: it resolves the service and maps HTTP."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_listing_review_service
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_review import Finding, Listing, ReviewedListing, Verdict

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


class UsageResponse(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: Decimal | None
    attempts: int


class ListingReviewResponse(BaseModel):
    findings: list[Finding]
    verdict: Verdict
    summary: str
    usage: UsageResponse
    cached: bool

    @classmethod
    def of(cls, reviewed: ReviewedListing) -> "ListingReviewResponse":
        return cls(
            findings=reviewed.review.findings,
            verdict=reviewed.review.verdict,
            summary=reviewed.review.summary,
            usage=UsageResponse(**vars(reviewed.usage)),
            cached=reviewed.cached,
        )


@router.post("/review", response_model=ListingReviewResponse)
async def review_listing(
    listing: Listing,
    service: Annotated[ListingReviewService, Depends(get_listing_review_service)],
) -> ListingReviewResponse:
    return ListingReviewResponse.of(await service.review(listing))
