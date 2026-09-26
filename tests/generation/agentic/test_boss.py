"""The boss is a function: no model, no mocks."""

from app.generation.agentic.boss import BossDecision, CriticMode, decide
from app.generation.agentic.critic import CriticResult, Problem, Rejection
from tests.generation.agentic.test_critic import a_finding


def a_result(confidence: float) -> CriticResult:
    return CriticResult(supported=[], confidence=confidence)


def test_enough_support_is_accepted() -> None:
    assert decide(a_result(0.8), attempt=1) == BossDecision.ACCEPT


def test_middling_support_on_the_first_attempt_sends_the_actor_back() -> None:
    assert decide(a_result(0.5), attempt=1) == BossDecision.RETRY


def test_middling_support_with_the_attempts_spent_goes_to_a_person() -> None:
    assert decide(a_result(0.5), attempt=2, max_attempts=2) == BossDecision.ESCALATE


def test_support_below_the_floor_goes_to_a_person_straight_away() -> None:
    assert decide(a_result(0.2), attempt=1) == BossDecision.ESCALATE


def test_the_thresholds_are_configuration() -> None:
    assert decide(a_result(0.6), attempt=1, min_confidence=0.5) == BossDecision.ACCEPT


# ── Flag mode (ADR 0035): a doubt goes to a person, nothing is removed ──────────────────────


def a_doubt(confidence: float) -> CriticResult:
    rejection = Rejection(
        finding=a_finding("La fianza supera una mensualidad"),
        problem=Problem.RULE_NOT_IN_SOURCES,
        reason="El fragmento no lo dice",
    )
    return CriticResult(supported=[], rejected=[rejection], confidence=confidence)


def test_in_flag_mode_a_doubt_goes_to_a_person_instead_of_back_to_the_actor() -> None:
    assert decide(a_doubt(0.5), attempt=1, mode=CriticMode.FLAG) == BossDecision.ESCALATE


def test_in_flag_mode_one_doubt_is_enough_to_ask_a_person() -> None:
    assert decide(a_doubt(0.9), attempt=1, mode=CriticMode.FLAG) == BossDecision.ESCALATE


def test_in_flag_mode_a_review_without_doubts_is_accepted() -> None:
    assert decide(a_result(1.0), attempt=1, mode=CriticMode.FLAG) == BossDecision.ACCEPT


def test_the_mode_filters_by_default() -> None:
    assert decide(a_doubt(0.5), attempt=1) == BossDecision.RETRY
