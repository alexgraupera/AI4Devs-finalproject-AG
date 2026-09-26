"""The agent conductor over a scripted model: citations, the unsourced-finding guardrail, the trace."""

from decimal import Decimal
from typing import Any

import pytest

from app.domain.agent_review_service import AgentReviewService
from app.domain.errors import NotAListing
from app.domain.schemas.listing_review import Listing, Verdict
from app.foundation.guardrails.input import InputGuardrailViolation
from app.foundation.guardrails.spend import BudgetExhausted
from app.generation.agentic.loop import SUBMIT
from tests.generation.agentic.test_loop import A_REVIEW, ScriptedModel, call, calls
from tests.generation.agentic.test_tools import FakeSearch

A_LISTING = Listing(
    text="Piso de dos habitaciones en Chamberí, con ascensor. Fianza de dos meses y honorarios a cargo del inquilino.",
    municipality="Madrid",
)


def review_with(*findings: dict[str, Any], verdict: str = "request_changes", is_listing: bool = True) -> dict[str, Any]:
    return {**A_REVIEW, "findings": list(findings), "verdict": verdict, "is_rental_listing": is_listing}


def finding(*, legal_basis: str | None, sources: list[int], severity: str = "high") -> dict[str, Any]:
    return {
        "category": "deposit_and_guarantees",
        "severity": severity,
        "message": "La fianza supera una mensualidad",
        "suggestion": "Pide una mensualidad",
        "legal_basis": legal_basis,
        "sources": sources,
    }


def service_for(review: dict[str, Any], **options: Any) -> AgentReviewService:
    model = ScriptedModel(calls(call("search_regulations", {"query": "fianza"})), calls(call(SUBMIT, review)))
    return AgentReviewService(model, FakeSearch(), **options)


async def test_a_legal_finding_ends_with_the_article_the_agent_retrieved() -> None:
    reviewed = await service_for(A_REVIEW).review(A_LISTING)

    (cited,) = reviewed.review.findings
    assert cited.legal_basis == "LAU art. 36.1"
    assert [c.url for c in cited.citations] == ["https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36"]


async def test_a_source_the_search_never_returned_is_dropped_from_the_citations() -> None:
    reviewed = await service_for(review_with(finding(legal_basis="LAU art. 36.1", sources=[36, 999]))).review(A_LISTING)

    assert [c.chunk_id for c in reviewed.review.findings[0].citations] == [36]


async def test_a_legal_finding_without_any_source_outside_the_checklist_never_reaches_the_user() -> None:
    unsourced = finding(legal_basis="LAU art. 17.4", sources=[])

    reviewed = await service_for(review_with(unsourced)).review(A_LISTING)

    assert reviewed.review.findings == []


async def test_a_checklist_point_may_stand_on_the_article_the_prompt_carries() -> None:
    reviewed = await service_for(review_with(finding(legal_basis="LAU art. 36.1", sources=[]))).review(A_LISTING)

    assert len(reviewed.review.findings) == 1


async def test_the_verdict_is_recomputed_when_the_only_high_finding_is_dropped() -> None:
    reviewed = await service_for(review_with(finding(legal_basis="LAU art. 17.4", sources=[]))).review(A_LISTING)

    assert reviewed.review.verdict == Verdict.APPROVE


async def test_a_quality_finding_needs_no_source() -> None:
    quality = finding(legal_basis=None, sources=[], severity="low")

    reviewed = await service_for(review_with(quality, verdict="approve")).review(A_LISTING)

    assert len(reviewed.review.findings) == 1


async def test_a_text_that_is_not_a_listing_is_rejected() -> None:
    with pytest.raises(NotAListing):
        await service_for(review_with(is_listing=False, verdict="approve")).review(A_LISTING)


async def test_the_input_guardrails_run_before_the_agent() -> None:
    model = ScriptedModel()

    with pytest.raises(InputGuardrailViolation):
        await AgentReviewService(model, FakeSearch()).review(Listing(text="Piso"))

    assert model.requests == []


async def test_an_exhausted_budget_stops_the_agent_before_its_first_call() -> None:
    class Exhausted:
        async def check(self) -> None:
            raise BudgetExhausted(retry_after=60)

        async def record(self, cost_usd: Decimal | None) -> None:
            return None

    model = ScriptedModel()

    with pytest.raises(BudgetExhausted):
        await AgentReviewService(model, FakeSearch(), spend=Exhausted()).review(A_LISTING)

    assert model.requests == []


async def test_the_trace_and_the_whole_cost_reach_the_caller() -> None:
    reviewed = await service_for(A_REVIEW).review(A_LISTING)

    assert [step.tool for step in reviewed.trace] == ["search_regulations", SUBMIT]
    assert reviewed.usage.estimated_cost_usd == Decimal("0.004")
