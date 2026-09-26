from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from app.domain.schemas.regulation_answer import AnswerCandidate
from app.foundation.guardrails.grounding import GroundingReport
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from evals.recording import RecordedCall, RecordingLLM, cost_by_stage

T = TypeVar("T", bound=BaseModel)


class FakeModel:
    def __init__(self, cost: str) -> None:
        self.cost = cost

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        usage = LLMUsage("anthropic", "claude-haiku-4-5", 10, 1, 5, Decimal(self.cost))
        return StructuredCompletion(output=None, usage=usage)  # type: ignore[arg-type]


async def test_two_models_sharing_a_list_add_up_to_one_answer() -> None:
    # Since #47 the generator and the grounding judge are two models; one answer is both.
    calls: list[RecordedCall] = []
    generator = RecordingLLM(FakeModel("0.004"), calls=calls)
    judge = RecordingLLM(FakeModel("0.001"), calls=calls)

    await generator.complete_structured(system="", user="", schema=AnswerCandidate)
    await judge.complete_structured(system="", user="", schema=GroundingReport)

    assert cost_by_stage(generator.drain()) == {"generation": 0.004, "grounding": 0.001}
    assert judge.calls == []
