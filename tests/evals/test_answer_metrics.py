"""The answer metrics over hand-built outcomes. They measure the measuring, not the answers."""

import pytest

from evals.answers.judge import AnswerJudgement, Grade, JudgedClaim, score
from evals.answers.metrics import AnswerOutcome, regression_passed, summarise

DEPOSIT = "BOE-A-1994-26003#a36"


def judged(
    *, correctness: float = 1.0, faithfulness_claims: tuple[bool, ...] = (True,), opening: bool = True
) -> object:
    grades = {1.0: Grade.YES, 0.5: Grade.PARTLY, 0.0: Grade.NO}
    return score(
        AnswerJudgement(
            analysis="",
            claims=[JudgedClaim(claim=f"claim {i}", supported=s) for i, s in enumerate(faithfulness_claims)],
            relevance=Grade.YES,
            correctness=grades[correctness],
            opening_holds=opening,
        )
    )


def answered(id: str = "q", **judge_args: object) -> AnswerOutcome:
    return AnswerOutcome(
        id=id,
        question="?",
        tags=[],
        expected=[DEPOSIT],
        answered=True,
        cited=[DEPOSIT],
        in_context=[DEPOSIT],
        judged=judged(**judge_args),  # type: ignore[arg-type]
        cost_by_stage={"generation": 0.004, "grounding": 0.001, "eval_judge": 0.003},
        latency_ms=5_000,
    )


def refused(id: str = "q", *, answerable: bool = True, rejected_by: str | None = None) -> AnswerOutcome:
    return AnswerOutcome(
        id=id,
        question="?",
        tags=[] if answerable else ["out-of-domain"],
        expected=[DEPOSIT] if answerable else [],
        answered=False,
        rejected_by=rejected_by,
        latency_ms=900,
    )


def test_faithfulness_is_counted_in_code_from_the_claims() -> None:
    result = judged(faithfulness_claims=(True, True, False))

    assert result.faithfulness == pytest.approx(2 / 3)  # type: ignore[attr-defined]
    assert result.unsupported == ["claim 2"]  # type: ignore[attr-defined]


def test_an_answer_without_legal_claims_is_not_marked_down() -> None:
    assert judged(faithfulness_claims=()).faithfulness == 1.0  # type: ignore[attr-defined]


def test_answered_rate_counts_only_answerable_questions() -> None:
    metrics = summarise([answered("a"), refused("b"), refused("ood", answerable=False)])

    assert metrics.answered_rate == 0.5


def test_a_guardrail_rejection_counts_as_a_refusal_of_an_out_of_domain_question() -> None:
    metrics = summarise([refused("ood", answerable=False, rejected_by="prompt_injection"), answered()])

    assert metrics.refusal_rate == 1.0


def test_an_out_of_domain_question_answered_lowers_the_refusal_rate() -> None:
    leak = AnswerOutcome(id="ood", question="?", tags=["out-of-domain"], expected=[], answered=True)

    assert summarise([leak, refused("ood2", answerable=False)]).refusal_rate == 0.5


def test_a_refusal_of_an_answerable_question_scores_zero_correctness() -> None:
    metrics = summarise([answered("a", correctness=1.0), refused("b")])

    assert metrics.correctness == 0.5


def test_citation_accuracy_needs_an_expected_article_among_the_citations() -> None:
    wrong = answered("wrong")
    wrong.cited = ["BOE-A-1994-26003#a20"]

    assert summarise([answered("right"), wrong]).citation_accuracy == 0.5


def test_the_service_cost_leaves_the_judge_out() -> None:
    assert answered().service_cost == pytest.approx(0.005)


def test_a_regression_case_passes_only_if_its_opening_holds() -> None:
    fixed = answered("fixed")
    fixed.tags = ["regression"]
    broken = answered("broken", opening=False)
    broken.tags = ["regression"]

    assert regression_passed(fixed)
    assert not regression_passed(broken)
    assert summarise([fixed, broken]).regressions_passed == 1


def test_a_refused_regression_case_fails() -> None:
    case = refused("regression")
    case.tags = ["regression"]

    assert not regression_passed(case)
