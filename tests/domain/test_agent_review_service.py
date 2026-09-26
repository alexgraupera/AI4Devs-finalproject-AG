"""The agent conductor over a scripted model: citations, the unsourced-finding guardrail, the trace."""

from decimal import Decimal
from typing import Any

import pytest

from app.domain.agent_review_service import AgentReviewService
from app.domain.errors import NotAListing
from app.domain.schemas.listing_review import Listing, Verdict
from app.foundation.guardrails.input import InputGuardrailViolation
from app.foundation.guardrails.spend import BudgetExhausted
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.agentic.boss import CriticMode
from app.generation.agentic.critic import CriticVerdict, FindingJudgement, Problem
from app.generation.agentic.loop import SUBMIT
from tests.generation.agentic.test_critic import judged
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


# ── Actor, critic, boss ─────────────────────────────────────────────────────────────────────


def two_passes(first: dict[str, Any], second: dict[str, Any] | None = None) -> ScriptedModel:
    """An actor that searches and submits, and does it again if the boss sends it back."""
    script = [calls(call("search_regulations", {"query": "fianza"})), calls(call(SUBMIT, first))]
    if second is not None:
        script += [calls(call("search_regulations", {"query": "fianza"})), calls(call(SUBMIT, second))]
    return ScriptedModel(*script)


def critic_of(*verdicts: list[bool]) -> "ScriptedJudge":
    return ScriptedJudge(
        *[
            [judged(i, ok, Problem.NONE if ok else Problem.RULE_NOT_IN_SOURCES) for i, ok in enumerate(v, start=1)]
            for v in verdicts
        ]
    )


class ScriptedJudge:
    """One critic verdict per call, in order."""

    def __init__(self, *verdicts: list[FindingJudgement]) -> None:
        self.verdicts = list(verdicts)
        self.calls = 0

    async def complete_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        self.calls += 1
        verdict = CriticVerdict(judgements=self.verdicts.pop(0))
        return StructuredCompletion(output=verdict, usage=A_CRITIC_USAGE)


A_CRITIC_USAGE = LLMUsage("openai", "gpt-5.4-mini", 2_000, 200, 900, Decimal("0.0024"))

TWO_FINDINGS = review_with(
    finding(legal_basis="LAU art. 36.1", sources=[36]),
    {**finding(legal_basis="LAU art. 36.1", sources=[36]), "message": "Inventada"},
)


async def test_a_finding_the_critic_rejects_never_reaches_the_user() -> None:
    # Three of four supported is 0.75, above the 0.7 the boss accepts at.
    four = review_with(*[{**finding(legal_basis="LAU art. 36.1", sources=[36]), "message": m} for m in "ABCD"])
    service = AgentReviewService(two_passes(four), FakeSearch(), critic=critic_of([True, True, True, False]))

    reviewed = await service.review(A_LISTING)

    assert [f.message for f in reviewed.review.findings] == ["A", "B", "C"]
    assert reviewed.dropped_findings == 1
    assert not reviewed.escalated


async def test_a_retry_sends_the_actor_back_with_the_rejections_quoted() -> None:
    model = two_passes(TWO_FINDINGS, review_with(finding(legal_basis="LAU art. 36.1", sources=[36])))
    service = AgentReviewService(model, FakeSearch(), critic=critic_of([True, False], [True]))

    reviewed = await service.review(A_LISTING)

    second_pass_prompt = model.requests[2]["messages"][1]["content"]
    assert "Un revisor ha comprobado tu revisión anterior" in second_pass_prompt
    assert "«Inventada»" in second_pass_prompt
    assert len(reviewed.review.findings) == 1 and not reviewed.escalated


async def test_support_that_stays_low_after_the_retry_goes_to_a_person() -> None:
    model = two_passes(TWO_FINDINGS, TWO_FINDINGS)
    service = AgentReviewService(model, FakeSearch(), critic=critic_of([True, False], [True, False]))

    reviewed = await service.review(A_LISTING)

    assert reviewed.escalated
    assert [f.message for f in reviewed.review.findings] == ["La fianza supera una mensualidad"]


async def test_the_verdict_is_recomputed_when_the_critic_drops_the_only_high_finding() -> None:
    service = AgentReviewService(two_passes(A_REVIEW), FakeSearch(), critic=critic_of([False]))

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.verdict == Verdict.APPROVE
    assert reviewed.escalated


# ── Flag mode (ADR 0035): what the critic doubts is kept, with its reason, for a person ───────


async def test_in_flag_mode_a_finding_the_critic_doubts_reaches_the_user_with_its_reason() -> None:
    four = review_with(*[{**finding(legal_basis="LAU art. 36.1", sources=[36]), "message": m} for m in "ABCD"])
    service = AgentReviewService(
        two_passes(four), FakeSearch(), critic=critic_of([True, True, True, False]), critic_mode=CriticMode.FLAG
    )

    reviewed = await service.review(A_LISTING)

    assert [f.message for f in reviewed.review.findings] == ["A", "B", "C", "D"]
    assert [(d.message, d.problem) for d in reviewed.disputed] == [("D", Problem.RULE_NOT_IN_SOURCES)]
    assert reviewed.dropped_findings == 0
    assert reviewed.escalated


async def test_in_flag_mode_the_actor_is_never_sent_back() -> None:
    model = two_passes(TWO_FINDINGS)
    service = AgentReviewService(model, FakeSearch(), critic=critic_of([True, False]), critic_mode=CriticMode.FLAG)

    reviewed = await service.review(A_LISTING)

    assert len(model.requests) == 2
    assert [f.message for f in reviewed.review.findings] == ["La fianza supera una mensualidad", "Inventada"]


async def test_in_flag_mode_a_doubted_high_finding_still_counts_for_the_verdict() -> None:
    service = AgentReviewService(
        two_passes(A_REVIEW), FakeSearch(), critic=critic_of([False]), critic_mode=CriticMode.FLAG
    )

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.verdict == Verdict.REQUEST_CHANGES
    assert reviewed.escalated


async def test_in_flag_mode_a_review_the_critic_backs_has_no_doubts() -> None:
    service = AgentReviewService(
        two_passes(A_REVIEW), FakeSearch(), critic=critic_of([True]), critic_mode=CriticMode.FLAG
    )

    reviewed = await service.review(A_LISTING)

    assert reviewed.disputed == [] and not reviewed.escalated


async def test_in_filter_mode_nothing_is_reported_as_disputed() -> None:
    service = AgentReviewService(two_passes(A_REVIEW), FakeSearch(), critic=critic_of([False]))

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.findings == [] and reviewed.disputed == []


async def test_the_critic_and_the_boss_appear_in_the_trace_and_the_critic_in_the_cost() -> None:
    service = AgentReviewService(two_passes(A_REVIEW), FakeSearch(), critic=critic_of([True]))

    reviewed = await service.review(A_LISTING)

    assert [step.tool for step in reviewed.trace] == ["search_regulations", SUBMIT, "critic", "boss"]
    assert reviewed.trace[-1].result == "Decisión: accept"
    assert reviewed.usage.estimated_cost_usd == Decimal("0.0064")


# ── Evidence: a finding about the listing must quote it ──────────────────────────────────────


async def test_a_finding_whose_quote_is_not_in_the_listing_never_reaches_the_user() -> None:
    invented = {**finding(legal_basis="LAU art. 20.1", sources=[36]), "evidence": "honorarios a cargo del inquilino"}
    listing = Listing(text="Estudio en Gràcia de 38 m², amueblado. Honorarios de agencia a cargo del propietario.")

    reviewed = await service_for(review_with(invented)).review(listing)

    assert reviewed.review.findings == []


async def test_a_finding_that_quotes_the_listing_is_kept() -> None:
    quoted = {**finding(legal_basis="LAU art. 36.1", sources=[36]), "evidence": "Fianza de dos meses"}

    reviewed = await service_for(review_with(quoted)).review(A_LISTING)

    assert len(reviewed.review.findings) == 1


async def test_a_quote_of_a_structured_field_counts_as_the_listing() -> None:
    quoted = {**finding(legal_basis=None, sources=[], severity="low"), "evidence": "Municipio: Madrid"}

    reviewed = await service_for(review_with(quoted, verdict="approve")).review(A_LISTING)

    assert len(reviewed.review.findings) == 1


# ── The corrected listing ────────────────────────────────────────────────────────────────────


async def test_the_rewrite_reaches_the_review_with_its_cost_and_its_step() -> None:
    from tests.generation.agentic.test_rewrite import ScriptedWriter

    writer = ScriptedWriter("Piso de dos habitaciones en Chamberí. Fianza de una mensualidad.")
    service = AgentReviewService(two_passes(A_REVIEW), FakeSearch(), critic=critic_of([True]), rewriter=writer)

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.rewrite is not None
    assert reviewed.review.rewrite.changes == ["Fianza ajustada a una mensualidad"]
    assert reviewed.trace[-1].tool == "rewrite"
    assert reviewed.usage.estimated_cost_usd == Decimal("0.0080")


async def test_a_review_without_findings_is_not_rewritten() -> None:
    from tests.generation.agentic.test_rewrite import ScriptedWriter

    writer = ScriptedWriter("")
    service = AgentReviewService(two_passes(review_with(verdict="approve")), FakeSearch(), rewriter=writer)

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.rewrite is None
    assert writer.calls == 0
