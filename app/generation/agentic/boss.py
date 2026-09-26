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


class CriticMode(StrEnum):
    """What a finding the critic does not back becomes (ADR 0035)."""

    # Removed before the user sees it; the actor may be sent back once (ADR 0025).
    FILTER = "filter"
    # Kept, with the critic's reason, and the review goes to a person. Measured on the other provider,
    # the critic still rejected correct findings, so its doubt is a question, not a verdict.
    FLAG = "flag"


def decide(
    result: CriticResult,
    *,
    attempt: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    escalate_below: float = DEFAULT_ESCALATE_BELOW,
    mode: CriticMode = CriticMode.FILTER,
) -> BossDecision:
    if mode == CriticMode.FLAG:
        # Nothing is removed and nobody is sent back: a retry is where correct findings got lost.
        return BossDecision.ESCALATE if result.rejected else BossDecision.ACCEPT
    if result.confidence >= min_confidence:
        return BossDecision.ACCEPT
    if result.confidence < escalate_below or attempt >= max_attempts:
        return BossDecision.ESCALATE
    return BossDecision.RETRY
