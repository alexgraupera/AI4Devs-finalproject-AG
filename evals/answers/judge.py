"""The judge of an answer: a model reads, code counts.

The model does what only reading can do: list the legal claims and say which the fragments
support, and grade relevance, correctness and the opening against a rubric with three levels. The
numbers (the share of supported claims, the mapping of a grade to a score) are computed here, not
asked for: a model asked for "a faithfulness between 0 and 1" returns a plausible decimal, not a
measurement.

The judge runs on the other provider from the one that wrote the answer by default, so it does not
share the writer's blind spots.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_eval_answer_judge_prompt

PROMPT_VERSION = "v1"


class Grade(StrEnum):
    YES = "yes"
    PARTLY = "partly"
    NO = "no"


SCORE: dict[Grade, float] = {Grade.YES: 1.0, Grade.PARTLY: 0.5, Grade.NO: 0.0}


class JudgedClaim(BaseModel):
    claim: str = Field(description="La afirmación jurídica, copiada de la respuesta")
    supported: bool = Field(description="True solo si los fragmentos la sostienen")


class AnswerJudgement(BaseModel):
    """What the judge fills. `analysis` goes first, so the grades follow from a reading."""

    analysis: str = Field(description="Dos o tres frases sobre la respuesta, antes de puntuar")
    claims: list[JudgedClaim] = Field(description="Las afirmaciones jurídicas de la respuesta")
    relevance: Grade = Field(description="¿Responde a lo que se preguntó?")
    correctness: Grade = Field(description="¿Dice lo mismo que la referencia?")
    opening_holds: bool = Field(description="¿La primera frase sigue siendo cierta al final?")


@dataclass(frozen=True)
class Judged:
    faithfulness: float
    relevance: float
    correctness: float
    opening_holds: bool
    analysis: str
    unsupported: list[str] = field(default_factory=list)
    usage: LLMUsage | None = None


def score(judgement: AnswerJudgement, usage: LLMUsage | None = None) -> Judged:
    claims = judgement.claims
    unsupported = [claim.claim for claim in claims if not claim.supported]
    # No legal claims means nothing unfaithful was said, which is not a reason to mark it down.
    faithfulness = (len(claims) - len(unsupported)) / len(claims) if claims else 1.0
    return Judged(
        faithfulness=faithfulness,
        relevance=SCORE[judgement.relevance],
        correctness=SCORE[judgement.correctness],
        opening_holds=judgement.opening_holds,
        analysis=judgement.analysis,
        unsupported=unsupported,
        usage=usage,
    )


async def judge_answer(
    llm: StructuredLLM,
    *,
    question: str,
    reference: str,
    context: str,
    answer: str,
    prompt_version: str = PROMPT_VERSION,
) -> Judged:
    system, user = render_eval_answer_judge_prompt(question, reference, context, answer, version=prompt_version)
    completion = await llm.complete_structured(system=system, user=user, schema=AnswerJudgement)
    return score(completion.output, completion.usage)
