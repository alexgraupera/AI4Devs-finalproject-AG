"""Does the cited article actually say what the answer claims it says?

The citation check of #23 is structural: it proves the article **was retrieved**. This one is
semantic: it proves the article **supports the sentence**. A model can cite a real article,
with a working BOE link, for a rule that article does not contain, and that failure is invisible
to everything upstream — the retrieval was right, the citation resolves, the link opens.

Two deterministic checks run first and cost nothing: an answer with no citation, or one citing a
fragment that is not in the context, is unsupported without asking anyone. Only what survives
those is worth a model call.

The policy is a **confidence threshold, not all-or-nothing**, and that was measured rather than
assumed. Refusing on any single unsupported claim rejected 23% of correct answers: the judge
flags framing sentences ("la información mínima depende de la comunidad autónoma"), negative
statements no fragment can ever support ("la LAU no regula la comisión"), and occasionally a
claim that is in the article after all. An assistant that refuses one good answer in four is
not a safer assistant, it is an unused one.

So an answer is published when the share of its supported claims clears the threshold, and the
prompt is told not to extract the kinds of sentence that produced those false positives.
"""

from dataclasses import dataclass, field

import structlog
from pydantic import BaseModel, Field

from app.domain.schemas.regulation_answer import RegulationAnswer
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_regulations_grounding_prompt
from app.generation.rag.context import Context

log = structlog.get_logger()

PROMPT_VERSION = "v1"

# Measured over the golden set: at 1.0 (refuse on any unsupported claim) 23% of correct answers
# were rejected, most of them over framing or negative statements. See ADR 0014.
DEFAULT_MIN_CONFIDENCE = 0.7

NO_CITATION = "the answer cites nothing"
CITATION_NOT_IN_CONTEXT = "the answer cites a fragment that was never retrieved"


class CheckedClaim(BaseModel):
    claim: str = Field(description="La afirmación jurídica, copiada de la respuesta")
    supported: bool = Field(description="True solo si los fragmentos citados la sostienen literalmente")
    reason: str = Field(default="", description="Por qué no la sostienen, si es que no")


class GroundingReport(BaseModel):
    claims: list[CheckedClaim] = Field(description="Una entrada por afirmación jurídica de la respuesta")


@dataclass(frozen=True)
class GroundingVerdict:
    supported: bool
    unsupported_claims: list[str] = field(default_factory=list)
    # Share of the legal claims the cited articles support. 1.0 when everything holds up.
    confidence: float = 1.0
    usage: LLMUsage | None = None
    # Set when a deterministic pre-check rejected the answer without a model call.
    rejected_by: str = ""


async def check_grounding(
    answer: RegulationAnswer,
    context: Context,
    llm: StructuredLLM,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> GroundingVerdict:
    if not answer.citations:
        return GroundingVerdict(supported=False, confidence=0.0, rejected_by=NO_CITATION)

    cited = [context.chunk_by_id(citation.chunk_id) for citation in answer.citations]
    if any(chunk is None for chunk in cited):
        return GroundingVerdict(supported=False, confidence=0.0, rejected_by=CITATION_NOT_IN_CONTEXT)

    sources = "\n\n".join(
        f"[{chunk.chunk_id}] {chunk.law_title} · {chunk.article_title}\n{chunk.text}"
        for chunk in cited
        if chunk is not None
    )
    system, user = render_regulations_grounding_prompt(answer.answer, sources, version=PROMPT_VERSION)

    try:
        completion = await llm.complete_structured(system=system, user=user, schema=GroundingReport)
    except Exception:
        # The judge being unavailable is not evidence that the answer is wrong. Failing open
        # keeps the service answering; the failure is logged so it can be counted.
        log.warning("grounding.unavailable", exc_info=True)
        return GroundingVerdict(supported=True, rejected_by="the grounding check could not run")

    claims = completion.output.claims
    unsupported = [claim.claim for claim in claims if not claim.supported]
    confidence = (len(claims) - len(unsupported)) / len(claims) if claims else 1.0

    return GroundingVerdict(
        # No claims at all means there was nothing to verify, which is not a reason to refuse.
        supported=confidence >= min_confidence,
        unsupported_claims=unsupported,
        confidence=confidence,
        usage=completion.usage,
    )
