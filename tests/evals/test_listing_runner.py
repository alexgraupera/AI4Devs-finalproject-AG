"""The runner over fake services: what it records from a review, a refusal and an outage."""

from decimal import Decimal

from app.domain.errors import LLMUnavailable, NotAListing
from app.domain.schemas.listing_agent_review import (
    AgentFinding,
    AgentReview,
    AgentReviewedListing,
    CitedFinding,
    StopReason,
    TraceStep,
)
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
from app.generation.agentic.critic import CriticResult, Problem, Rejection, critic_step
from app.generation.agentic.ports import RegulationFragment
from app.generation.agentic.tools import SearchRegulations
from evals.listings.dataset import AnnotatedListing
from evals.listings.metrics import ListingOutcome, summarise
from evals.listings.run import articles_read, critic_rejections, render, review_with_agent, review_with_pipeline
from tests.generation.agentic.test_tools import FakeSearch, a_fragment

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


async def test_the_articles_read_come_from_what_the_search_tool_returned() -> None:
    catalan = RegulationFragment(
        chunk_id=245,
        text="Artículo 61. Oferta para el arrendamiento.",
        score=0.6,
        law_id="BOE-A-2008-3657",
        law_title="Ley 18/2007, de 28 de diciembre, del derecho a la vivienda.",
        article_title="Artículo 61",
        citation_url="https://www.boe.es/#a61",
        jurisdiction="catalonia",
    )
    result = await SearchRegulations(FakeSearch([a_fragment(36), catalan])).run({"query": "oferta"})
    trace = [TraceStep(step=1, tool="search_regulations", result=result.content)]

    assert articles_read(trace) == {("LAU", "36"), ("Ley 18/2007", "61")}


def test_the_critic_rejections_are_read_from_its_step_with_their_article() -> None:
    offer = AgentFinding(
        category=FindingCategory.OTHER,
        severity=Severity.HIGH,
        message="Falta el plazo del arrendamiento.",
        suggestion="Indícalo.",
        legal_basis="Ley 18/2007 art. 61.2",
    )
    step = critic_step(5, CriticResult(supported=[], rejected=[Rejection(offer, Problem.WRONG_ARTICLE, "no")]))

    assert critic_rejections([step]) == [(("Ley 18/2007", "61"), "wrong_article")]


def test_repeated_runs_of_a_listing_are_reported_together() -> None:
    first = ListingOutcome(
        id="deposit",
        tags=[],
        expected={("LAU", "36")},
        expected_verdict="request_changes",
        expected_error=None,
        found={("LAU", "36")},
        verdict="request_changes",
    )
    second = ListingOutcome(
        id="deposit",
        tags=[],
        expected={("LAU", "36")},
        expected_verdict="request_changes",
        expected_error=None,
        verdict="approve",
        repeat=2,
    )

    report = render({"agent": (summarise([first, second]), [first, second])})

    assert "| `deposit` | LAU 36 | LAU 36 (1/2) |  | ❌ approve (1/2) |" in report
    assert "by repeat: F1 1.00, 0.00" in report
