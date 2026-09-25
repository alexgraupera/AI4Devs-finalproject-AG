"""Transport for the listing review. No business logic: it resolves the service and maps HTTP."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.api.security import enforce_rate_limit
from app.dependencies import get_agent_review_service, get_listing_review_service
from app.domain.agent_review_service import AgentReviewService
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_agent_review import (
    AgentReviewedListing,
    CitedFinding,
    HumanAction,
    HumanDecision,
    HumanReviewRequest,
    StopReason,
    TraceStep,
)
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
    # completed, waiting_human (a person has to decide before it is published) or discarded.
    status: str
    run_id: str | None
    findings: list[CitedFinding]
    verdict: Verdict
    summary: str
    # Every step the agent took, so a review can be followed from the listing to each citation.
    trace: list[TraceStep]
    stop_reason: StopReason
    # The critic could not back every conclusion: a person has to check this review.
    escalated: bool
    # Findings the critic removed because the listing or the cited articles did not hold them.
    dropped_findings: int
    pending_review: HumanReviewRequest | None
    human_decision: HumanDecision | None
    usage: UsageResponse

    @classmethod
    def of(cls, reviewed: AgentReviewedListing) -> "AgentReviewResponse":
        if reviewed.pending_review is not None:
            status = "waiting_human"
        elif reviewed.human_decision is not None and reviewed.human_decision.action == HumanAction.REJECT:
            status = "discarded"
        else:
            status = "completed"
        return cls(
            status=status,
            run_id=reviewed.run_id,
            findings=reviewed.review.findings,
            verdict=reviewed.review.verdict,
            summary=reviewed.review.summary,
            trace=reviewed.trace,
            stop_reason=reviewed.stop_reason,
            escalated=reviewed.escalated,
            dropped_findings=reviewed.dropped_findings,
            pending_review=reviewed.pending_review,
            human_decision=reviewed.human_decision,
            usage=UsageResponse(**vars(reviewed.usage)),
        )


@router.post("/agent-review", response_model=AgentReviewResponse)
async def agent_review_listing(
    listing: Listing,
    response: Response,
    service: Annotated[AgentReviewService, Depends(get_agent_review_service)],
) -> AgentReviewResponse:
    """The same listing, reviewed by an agent that consults the regulations before deciding.

    Next to `/review`, not instead of it: both paths stay live so they can be compared (#52). A
    review the agent cannot stand behind pauses and answers 202: it waits for a person.
    """
    reviewed = await service.review(listing)
    if reviewed.pending_review is not None:
        response.status_code = 202
    return AgentReviewResponse.of(reviewed)


@router.get("/agent-review/{run_id}", response_model=AgentReviewResponse)
async def pending_agent_review(
    run_id: str,
    service: Annotated[AgentReviewService, Depends(get_agent_review_service)],
) -> AgentReviewResponse:
    """A paused review as it stands, so the page can be reloaded without losing the decision to make."""
    return AgentReviewResponse.of(await service.pending(run_id))


@router.post("/agent-review/{run_id}/resume", response_model=AgentReviewResponse)
async def resume_agent_review(
    run_id: str,
    decision: HumanDecision,
    service: Annotated[AgentReviewService, Depends(get_agent_review_service)],
) -> AgentReviewResponse:
    """A person's decision on a paused review: approve it, keep only some findings, or discard it."""
    return AgentReviewResponse.of(await service.resume(run_id, decision))
