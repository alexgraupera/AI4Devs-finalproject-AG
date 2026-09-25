"""The boss is a function: no model, no mocks."""

from app.generation.agentic.boss import BossDecision, decide
from app.generation.agentic.critic import CriticResult


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
