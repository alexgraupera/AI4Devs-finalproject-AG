from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from app.domain.schemas.regulation_answer import Citation, RegulationAnswer
from app.foundation.guardrails.grounding import (
    CITATION_NOT_IN_CONTEXT,
    NO_CITATION,
    CheckedClaim,
    GroundingReport,
    check_grounding,
)
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.rag.context import build_context
from app.generation.rag.retriever import RetrievedChunk

T = TypeVar("T", bound=BaseModel)

A_USAGE = LLMUsage(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=1_500,
    output_tokens=120,
    latency_ms=800,
    estimated_cost_usd=Decimal("0.0021"),
)


def a_chunk(chunk_id: int = 36) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="Artículo 36. Fianza. Una mensualidad de renta en el arrendamiento de viviendas.",
        score=0.72,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994",
        article_title="Artículo 36",
        block_id="a36",
        jurisdiction="state",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        fecha_vigencia="20190306",
    )


def an_answer(*, cited: list[int] | None = None, text: str = "La fianza es de una mensualidad.") -> RegulationAnswer:
    ids = [36] if cited is None else cited
    return RegulationAnswer(
        answer=text,
        citations=[Citation.of(a_chunk(chunk_id)) for chunk_id in ids],
        has_answer=True,
    )


class FakeJudge:
    def __init__(self, report: GroundingReport | None = None, error: Exception | None = None) -> None:
        self.report = report if report is not None else GroundingReport(claims=[])
        self.error = error
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.calls += 1
        self.prompts.append((system, user))
        if self.error is not None:
            raise self.error
        return StructuredCompletion(output=self.report, usage=A_USAGE)  # type: ignore[arg-type]


def supported(*claims: str) -> GroundingReport:
    return GroundingReport(claims=[CheckedClaim(claim=c, supported=True) for c in claims])


def with_unsupported(claim: str, reason: str = "el artículo dice otra cosa") -> GroundingReport:
    return GroundingReport(
        claims=[
            CheckedClaim(claim="La fianza es obligatoria", supported=True),
            CheckedClaim(claim=claim, supported=False, reason=reason),
        ]
    )


async def test_an_answer_with_no_citation_fails_without_spending_a_call() -> None:
    judge = FakeJudge()

    verdict = await check_grounding(
        RegulationAnswer(answer="La fianza es de tres meses.", citations=[], has_answer=True),
        build_context([a_chunk()]),
        judge,
    )

    assert not verdict.supported
    assert verdict.rejected_by == NO_CITATION
    assert judge.calls == 0


async def test_a_citation_outside_the_context_fails_without_spending_a_call() -> None:
    judge = FakeJudge()

    verdict = await check_grounding(an_answer(cited=[999]), build_context([a_chunk()]), judge)

    assert not verdict.supported
    assert verdict.rejected_by == CITATION_NOT_IN_CONTEXT
    assert judge.calls == 0


async def test_a_supported_answer_passes() -> None:
    judge = FakeJudge(supported("La fianza es de una mensualidad"))

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), judge)

    assert verdict.supported
    assert verdict.unsupported_claims == []
    assert verdict.confidence == 1.0


async def test_an_answer_mostly_unsupported_is_refused() -> None:
    judge = FakeJudge(with_unsupported("La fianza es de tres mensualidades"))

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), judge)

    assert not verdict.supported
    assert verdict.unsupported_claims == ["La fianza es de tres mensualidades"]
    assert verdict.confidence == 0.5


async def test_one_flagged_claim_among_many_does_not_sink_a_good_answer() -> None:
    # Measured: refusing on any single unsupported claim rejected 23% of correct answers,
    # mostly over framing sentences the judge should not have extracted at all.
    claims = [CheckedClaim(claim=f"afirmación {i}", supported=i < 9) for i in range(10)]

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), FakeJudge(GroundingReport(claims=claims)))

    assert verdict.supported
    assert verdict.confidence == 0.9
    assert verdict.unsupported_claims == ["afirmación 9"]


async def test_the_threshold_is_where_the_line_is_drawn() -> None:
    claims = [CheckedClaim(claim=f"afirmación {i}", supported=i < 7) for i in range(10)]
    report = GroundingReport(claims=claims)

    lenient = await check_grounding(an_answer(), build_context([a_chunk()]), FakeJudge(report), min_confidence=0.7)
    strict = await check_grounding(an_answer(), build_context([a_chunk()]), FakeJudge(report), min_confidence=0.8)

    assert lenient.supported
    assert not strict.supported


async def test_an_answer_with_nothing_to_verify_is_not_refused() -> None:
    # No legal claims extracted means there was nothing to check, not that the check failed.
    judge = FakeJudge(GroundingReport(claims=[]))

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), judge)

    assert verdict.supported
    assert verdict.confidence == 1.0


async def test_the_judge_being_down_does_not_condemn_the_answer() -> None:
    # The judge being unavailable is not evidence that the answer is wrong.
    judge = FakeJudge(error=RuntimeError("provider is down"))

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), judge)

    assert verdict.supported
    assert "could not run" in verdict.rejected_by


async def test_the_cited_article_and_the_answer_both_reach_the_judge() -> None:
    judge = FakeJudge(supported("x"))

    await check_grounding(an_answer(text="La fianza es de una mensualidad."), build_context([a_chunk()]), judge)

    _, user = judge.prompts[0]
    assert "Artículo 36. Fianza." in user
    assert "La fianza es de una mensualidad." in user


async def test_what_the_check_cost_travels_with_the_verdict() -> None:
    judge = FakeJudge(supported("x"))

    verdict = await check_grounding(an_answer(), build_context([a_chunk()]), judge)

    assert verdict.usage is not None
    assert verdict.usage.input_tokens == 1_500
