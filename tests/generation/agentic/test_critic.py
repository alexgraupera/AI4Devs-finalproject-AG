"""The critic over a scripted judge: what it keeps, what it drops, what it costs."""

from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from app.domain.schemas.listing_agent_review import AgentFinding
from app.domain.schemas.listing_review import FindingCategory, Listing, Severity
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.agentic.critic import CriticVerdict, FindingJudgement, Problem, criticise
from tests.generation.agentic.test_tools import a_fragment

T = TypeVar("T", bound=BaseModel)

A_LISTING = Listing(
    text="Estudio de 38 m² en Gràcia. Certificado energético D. Fianza de dos meses.", energy_rating="D"
)
A_USAGE = LLMUsage("openai", "gpt-5.4-mini", 2_000, 200, 900, Decimal("0.0024"))


def a_finding(
    message: str, *, legal_basis: str | None = "LAU art. 36.1", sources: list[int] | None = None
) -> AgentFinding:
    return AgentFinding(
        category=FindingCategory.DEPOSIT_AND_GUARANTEES,
        severity=Severity.HIGH,
        message=message,
        suggestion="Corrígelo",
        legal_basis=legal_basis,
        sources=[36] if sources is None else sources,
    )


class ScriptedJudge:
    def __init__(self, *judgements: FindingJudgement, error: Exception | None = None) -> None:
        self.judgements = list(judgements)
        self.error = error
        self.user: str | None = None

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.user = user
        if self.error is not None:
            raise self.error
        return StructuredCompletion(output=CriticVerdict(judgements=self.judgements), usage=A_USAGE)  # type: ignore[arg-type]


def judged(index: int, supported: bool, problem: Problem = Problem.NONE) -> FindingJudgement:
    return FindingJudgement(finding_index=index, supported=supported, problem=problem, reason="porque sí")


FRAGMENTS = {36: a_fragment(36)}


async def test_a_supported_finding_survives() -> None:
    result = await criticise([a_finding("Fianza de dos meses")], A_LISTING, FRAGMENTS, ScriptedJudge(judged(1, True)))

    assert [f.message for f in result.supported] == ["Fianza de dos meses"]
    assert result.confidence == 1.0
    assert result.usage == A_USAGE


async def test_a_finding_the_listing_contradicts_is_rejected_with_its_problem() -> None:
    # The error of the first hand check of #38: a rating reported missing that the listing states.
    missing_rating = a_finding("Falta la calificación energética", legal_basis="RD 390/2021 art. 15.2")
    judge = ScriptedJudge(judged(1, True), judged(2, False, Problem.CONTRADICTS_LISTING))

    result = await criticise([a_finding("Fianza de dos meses"), missing_rating], A_LISTING, FRAGMENTS, judge)

    assert [r.finding.message for r in result.rejected] == ["Falta la calificación energética"]
    assert result.rejected[0].problem == Problem.CONTRADICTS_LISTING
    assert result.confidence == 0.5


async def test_the_judge_reads_the_listing_and_the_text_of_the_cited_fragments() -> None:
    judge = ScriptedJudge(judged(1, True))

    await criticise([a_finding("Fianza de dos meses")], A_LISTING, FRAGMENTS, judge)

    assert judge.user is not None
    assert "Certificado energético D" in judge.user
    assert "Una mensualidad de renta" in judge.user


async def test_judgements_for_findings_that_do_not_exist_are_ignored() -> None:
    result = await criticise(
        [a_finding("Fianza")], A_LISTING, FRAGMENTS, ScriptedJudge(judged(1, True), judged(7, False))
    )

    assert result.rejected == []


async def test_a_finding_the_critic_did_not_judge_is_kept() -> None:
    result = await criticise([a_finding("A"), a_finding("B")], A_LISTING, FRAGMENTS, ScriptedJudge(judged(1, True)))

    assert len(result.supported) == 2


async def test_no_findings_means_no_call_and_nothing_to_doubt() -> None:
    judge = ScriptedJudge()

    result = await criticise([], A_LISTING, FRAGMENTS, judge)

    assert result.confidence == 1.0
    assert judge.user is None


async def test_a_critic_that_cannot_run_keeps_everything_and_says_so() -> None:
    result = await criticise([a_finding("Fianza")], A_LISTING, FRAGMENTS, ScriptedJudge(error=TimeoutError()))

    assert result.unavailable
    assert len(result.supported) == 1
