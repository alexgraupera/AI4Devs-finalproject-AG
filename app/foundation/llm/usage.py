"""What a call cost us, carried next to what it produced.

A call is not always one round trip: when the answer does not fit the schema, Instructor asks
again, and every attempt is billed. Reporting only the last one would hide exactly the cost
that hurts, so attempts are accumulated per call.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class LLMUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: Decimal | None
    attempts: int = 1


def combined(first: LLMUsage, second: LLMUsage | None) -> LLMUsage:
    """One answer, two model calls: report the sum, or the cost dashboard undercounts."""
    if second is None:
        return first
    costs = [c for c in (first.estimated_cost_usd, second.estimated_cost_usd) if c is not None]
    return LLMUsage(
        provider=first.provider,
        model=first.model,
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        latency_ms=first.latency_ms + second.latency_ms,
        estimated_cost_usd=sum(costs, Decimal(0)) if costs else None,
        attempts=first.attempts + second.attempts,
    )


@dataclass(frozen=True)
class StructuredCompletion[T: BaseModel]:
    output: T
    usage: LLMUsage


@dataclass
class UsageAccumulator:
    """Tokens billed so far for one call, across every attempt it needed."""

    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0
    models: list[str] = field(default_factory=list)

    def record(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        self.attempts += 1
        self.input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        model = getattr(response, "model", None)
        if model:
            self.models.append(str(model))

    @property
    def model(self) -> str | None:
        """The model that produced the accepted answer: the last one to reply."""
        return self.models[-1] if self.models else None


# One accumulator per call, isolated per task: two reviews in flight must not add up together.
current_usage: ContextVar[UsageAccumulator | None] = ContextVar("current_usage", default=None)
