"""Transport for the listing review. No business logic: it resolves the service and maps HTTP."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.security import enforce_rate_limit
from app.dependencies import get_agent_review_service, get_listing_review_service
from app.domain.agent_review_service import AgentReviewService
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_agent_review import AgentReviewedListing, CitedFinding, StopReason, TraceStep
from app.domain.schemas.listing_review import Finding, Listing, ReviewedListing, Verdict

# The same guards as the regulations router: the review is the most-called endpoint and every
# review is a model call, so it is the one an open door would cost the most.
router = APIRouter(prefix="/api/v1/listings", tags=["listings"], dependencies=[Depends(enforce_rate_limit)])


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


class AgentReviewResponse(BaseModel):
    findings: list[CitedFinding]
    verdict: Verdict
    summary: str
    # Every step the agent took, so a review can be followed from the listing to each citation.
    trace: list[TraceStep]
    stop_reason: StopReason
    usage: UsageResponse

    @classmethod
    def of(cls, reviewed: AgentReviewedListing) -> "AgentReviewResponse":
        return cls(
            findings=reviewed.review.findings,
            verdict=reviewed.review.verdict,
            summary=reviewed.review.summary,
            trace=reviewed.trace,
            stop_reason=reviewed.stop_reason,
            usage=UsageResponse(**vars(reviewed.usage)),
        )


@router.post("/agent-review", response_model=AgentReviewResponse)
async def agent_review_listing(
    listing: Listing,
    service: Annotated[AgentReviewService, Depends(get_agent_review_service)],
) -> AgentReviewResponse:
    """The same listing, reviewed by an agent that consults the regulations before deciding.

    Next to `/review`, not instead of it: both paths stay live so they can be compared (#52).
    """
    return AgentReviewResponse.of(await service.review(listing))
