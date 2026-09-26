"""The boss: accept, send back, or hand to a person. A function, not a model.

Three outcomes and two thresholds are an `if`, and a model here would add cost, latency and a
failure mode to a decision code already expresses exactly. The session's boss is "little more than
a loop", with a maximum number of attempts and a defined behaviour when they run out: here, a
person.
"""

from enum import StrEnum

from app.generation.agentic.critic import CriticResult

DEFAULT_MIN_CONFIDENCE = 0.7
DEFAULT_ESCALATE_BELOW = 0.4
DEFAULT_MAX_ATTEMPTS = 2


class BossDecision(StrEnum):
    ACCEPT = "accept"
    RETRY = "retry"
    ESCALATE = "escalate"


def decide(
    result: CriticResult,
    *,
    attempt: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    escalate_below: float = DEFAULT_ESCALATE_BELOW,
) -> BossDecision:
    if result.confidence >= min_confidence:
        return BossDecision.ACCEPT
    if result.confidence < escalate_below or attempt >= max_attempts:
        return BossDecision.ESCALATE
    return BossDecision.RETRY
