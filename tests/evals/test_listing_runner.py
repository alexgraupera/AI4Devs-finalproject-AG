"""The runner over fake services: what it records from a review, a refusal and an outage."""

from decimal import Decimal

from app.domain.errors import LLMUnavailable, NotAListing
from app.domain.schemas.listing_agent_review import AgentReview, AgentReviewedListing, CitedFinding, StopReason
from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    Listing,
    ListingReview,
    ReviewedListing,
    Severity,
    Verdict,
)
from app.domain.schemas.regulation_answer import Citation
from app.foundation.guardrails.input import InputGuardrailViolation
from app.foundation.guardrails.output import check_review
from app.foundation.llm.usage import LLMUsage
from evals.listings.dataset import AnnotatedListing
from evals.listings.metrics import summarise
from evals.listings.run import render, review_with_agent, review_with_pipeline

USAGE = LLMUsage(
    provider="openai",
    model="gpt-5.4-mini",
    input_tokens=100,
    output_tokens=10,
    latency_ms=10,
    estimated_cost_usd=Decimal("0.004"),
)

CASE = AnnotatedListing(
    id="deposit",
    listing=Listing(
        text="Piso luminoso en Valencia, dos habitaciones, fianza de dos meses. " * 2, price_eur_month=Decimal(900)
    ),
    tags=["violation", "deposit"],
    expected_legal={("LAU", "36")},
    expected_verdict="request_changes",
)


def finding(legal_basis: str | None) -> Finding:
    return Finding(
        category=FindingCategory.DEPOSIT_AND_GUARANTEES,
        severity=Severity.HIGH,
        message="La fianza excede una mensualidad.",
        suggestion="Pide una mensualidad.",
        legal_basis=legal_basis,
    )


class Pipeline:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def review(self, listing: Listing) -> ReviewedListing:
        if self.error:
            raise self.error
        review = ListingReview(
            findings=[finding("LAU art. 36.1"), finding(None), finding("Código Civil art. 1555")],
            verdict=Verdict.REQUEST_CHANGES,
            summary="Fianza.",
        )
        # The real service, as far as the output guardrail goes.
        return ReviewedListing(review=check_review(review), usage=USAGE)


async def test_the_pipeline_records_the_legal_findings_and_the_cost() -> None:
    outcome = await review_with_pipeline(CASE, Pipeline())
    assert outcome.found == {("LAU", "36")}
    assert outcome.notes == [(("LAU", "36"), "La fianza excede una mensualidad.")]
    assert outcome.verdict == "request_changes"
    assert outcome.cost_usd == 0.004
    assert outcome.dropped == 1
    assert outcome.error is None


async def test_a_refusal_is_recorded_as_its_reason() -> None:
    injection = InputGuardrailViolation("no", reason="prompt_injection")
    assert (await review_with_pipeline(CASE, Pipeline(injection))).error == "prompt_injection"
    assert (await review_with_pipeline(CASE, Pipeline(NotAListing()))).error == "not_a_listing"
    assert (await review_with_pipeline(CASE, Pipeline(LLMUnavailable("down")))).error == "LLMUnavailable"


class Agent:
    async def review(self, listing: Listing) -> AgentReviewedListing:
        cited = CitedFinding(
            **finding(None).model_dump(),
            citations=[
                Citation(
                    law_id="BOE-A-1994-26003",
                    law_title="LAU",
                    article="Artículo 36. Fianza.",
                    url="https://www.boe.es/#a36",
                    chunk_id=36,
                )
            ],
        )
        review = AgentReview(findings=[cited], verdict=Verdict.REQUEST_CHANGES, summary="Fianza.")
        return AgentReviewedListing(
            review=review, trace=[], usage=USAGE, stop_reason=StopReason.COMPLETED, escalated=True, dropped_findings=2
        )


async def test_the_agent_names_a_finding_by_its_citation_when_its_basis_does_not() -> None:
    outcome = await review_with_agent(CASE, Agent())
    assert outcome.found == {("LAU", "36")}
    assert outcome.escalated
    assert outcome.dropped == 2


async def test_the_report_lists_what_each_listing_missed() -> None:
    outcome = await review_with_pipeline(CASE, Pipeline())
    outcome.found = set()
    report = render({"cag": (summarise([outcome]), [outcome])})
    assert "| `deposit` | LAU 36 | LAU 36 |  | ✅ |" in report


async def test_the_report_quotes_the_findings_outside_the_annotation() -> None:
    outcome = await review_with_pipeline(CASE, Pipeline())
    outcome.expected = {("RD 390/2021", "15")}
    report = render({"cag": (summarise([outcome]), [outcome])})
    assert "- `deposit` · LAU 36: La fianza excede una mensualidad." in report
