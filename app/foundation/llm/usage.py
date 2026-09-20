"""What a call cost us, carried next to what it produced."""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel


@dataclass(frozen=True)
class LLMUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: Decimal | None


@dataclass(frozen=True)
class StructuredCompletion[T: BaseModel]:
    output: T
    usage: LLMUsage
