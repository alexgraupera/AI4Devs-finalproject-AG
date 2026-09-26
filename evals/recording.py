"""What each stage of an answer cost, without the service having to report it that way.

The service sums its model calls into one `LLMUsage` per answer, which is right for a response and
useless for an evaluation that has to say *which* step is expensive. This wrapper sits between the
service and the model and writes down every call, named by the schema it asked for, so the report
can split the cost into rerank, generation and grounding without the service knowing it is being
measured.
"""

from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.foundation.llm.wrapper import StructuredLLM

T = TypeVar("T", bound=BaseModel)

# The schema a call asks for says which step made it.
STAGES: dict[str, str] = {
    "Ranking": "rerank",
    "AnswerCandidate": "generation",
    "GroundingReport": "grounding",
    "ReviewCandidate": "review",
    "AnswerJudgement": "eval_judge",
}


@dataclass(frozen=True)
class RecordedCall:
    stage: str
    usage: LLMUsage


class RecordingLLM:
    def __init__(self, inner: StructuredLLM) -> None:
        self._inner = inner
        self.calls: list[RecordedCall] = []

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        completion = await self._inner.complete_structured(system=system, user=user, schema=schema)
        self.calls.append(RecordedCall(stage=STAGES.get(schema.__name__, schema.__name__), usage=completion.usage))
        return completion

    def drain(self) -> list[RecordedCall]:
        """The calls since the last drain: one question's worth, when drained after each one."""
        calls, self.calls = self.calls, []
        return calls


def cost_by_stage(calls: list[RecordedCall]) -> dict[str, float]:
    costs: dict[str, float] = {}
    for call in calls:
        costs[call.stage] = costs.get(call.stage, 0.0) + float(call.usage.estimated_cost_usd or 0)
    return costs
