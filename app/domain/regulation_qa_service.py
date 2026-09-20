"""The conductor of a regulation answer: retrieve, assemble, ask, and check what came back.

The order is the point, and so is what happens when a step finds nothing:

- Nothing retrieved above the threshold means **no LLM call at all**. A model handed an empty
  context will still write something, and that something is exactly what this product must not
  produce.
- A citation the retrieval never returned is **dropped**, not trusted. The model cites by the
  numbers it was shown; anything else is invention.
- An answer left with no valid citation becomes "I don't know". An answer nobody can check is
  worth less than an admission of ignorance, because the reader cannot tell them apart.
"""

import re
import time
from decimal import Decimal

import structlog

from app.domain.schemas.regulation_answer import (
    AnswerCandidate,
    AnsweredQuestion,
    Citation,
    RegulationAnswer,
    RegulationQuestion,
)
from app.foundation.guardrails.input import QUESTION, ModerationClient, check_input
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_regulations_qa_prompt
from app.generation.rag.context import DEFAULT_MAX_CHARS, Context, build_context
from app.generation.rag.retriever import RetrievedChunk, Retriever

log = structlog.get_logger()

PROMPT_VERSION = "v2"

# Shown when the corpus does not answer the question. The same sentence for "nothing retrieved",
# "the model said it cannot answer" and "the citations did not hold up": from the reader's side
# they are the same fact, and distinguishing them would only hint at an answer we do not have.
#
# It names what the corpus does cover. A refusal that only says "not found" is a dead end:
# someone asking about rental income tax cannot tell whether they phrased it badly or asked
# about something outside the four laws this assistant reads.
NO_ANSWER = (
    "No he encontrado la respuesta en la normativa que tengo indexada, que es la Ley de "
    "Arrendamientos Urbanos, la Ley 12/2023 por el derecho a la vivienda, el Real Decreto "
    "390/2021 del certificado energético y la Ley 18/2007 del derecho a la vivienda de Cataluña. "
    "Si tu pregunta es sobre fiscalidad, comunidades de propietarios o procedimientos judiciales, "
    "queda fuera de lo que puedo consultar: pregunta a un profesional."
)

# The context numbers fragments so the model can cite them by id, and the model sometimes copies
# that number into the prose. "[38]" means nothing to the person reading, so it is removed here
# rather than hoped away in the prompt: a rule the model follows most of the time is not a rule.
_CHUNK_MARKER = re.compile(r"\s*\[\s*\d+\s*\]")


class RegulationQAService:
    def __init__(
        self,
        llm: StructuredLLM,
        retriever: Retriever,
        moderation: ModerationClient | None = None,
        *,
        model: str = "",
        prompt_version: str = PROMPT_VERSION,
        top_k: int | None = None,
        min_score: float | None = None,
        max_context_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._moderation = moderation
        self._model = model
        self._prompt_version = prompt_version
        self._top_k = top_k
        self._min_score = min_score
        self._max_context_chars = max_context_chars

    async def ask(self, question: RegulationQuestion) -> AnsweredQuestion:
        await check_input(question.question, moderation=self._moderation, limits=QUESTION)

        started = time.perf_counter()
        chunks = await self._retriever.search(
            question.question,
            k=self._top_k,
            min_score=self._min_score,
            jurisdictions=question.jurisdictions,
        )
        context = build_context(chunks, max_chars=self._max_context_chars)

        if context.is_empty:
            log.info("regulations_qa.no_context", question_chars=len(question.question))
            return self._refusal(chunks, latency_ms=int((time.perf_counter() - started) * 1000))

        system, user = render_regulations_qa_prompt(question.question, context.text, version=self._prompt_version)
        completion = await self._llm.complete_structured(system=system, user=user, schema=AnswerCandidate)
        usage = completion.usage
        candidate = completion.output

        citations = self._verified_citations(candidate, context)
        # Cleaned before it is judged: an answer that is nothing but fragment markers is empty
        # once they are removed, and an empty answer is a refusal, not an answer.
        answer = self._readable(candidate.answer)
        answered = candidate.has_answer and bool(citations) and bool(answer)

        log.info(
            "regulations_qa.completed",
            prompt_version=self._prompt_version,
            model=usage.model,
            retrieved=len(chunks),
            in_context=len(context.chunks),
            cited=len(citations),
            claimed_answer=candidate.has_answer,
            has_answer=answered,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
            estimated_cost_usd=float(usage.estimated_cost_usd) if usage.estimated_cost_usd is not None else None,
        )

        if not answered:
            return AnsweredQuestion(answer=self._no_answer(), usage=usage, retrieved=chunks)

        return AnsweredQuestion(
            answer=RegulationAnswer(answer=answer, citations=citations, has_answer=True),
            usage=usage,
            retrieved=chunks,
        )

    def _readable(self, answer: str) -> str:
        """Strip the fragment numbers the model sometimes copies into the prose."""
        cleaned = _CHUNK_MARKER.sub("", answer).strip()
        if cleaned != answer.strip():
            log.info("regulations_qa.stripped_chunk_marker", model=self._model)
        return cleaned

    def _verified_citations(self, candidate: AnswerCandidate, context: Context) -> list[Citation]:
        """Resolve the cited numbers against what was actually retrieved, dropping the rest."""
        citations = []
        for chunk_id in dict.fromkeys(candidate.cited_chunk_ids):
            chunk = context.chunk_by_id(chunk_id)
            if chunk is None:
                log.warning("regulations_qa.invented_citation", chunk_id=chunk_id, model=self._model)
                continue
            citations.append(Citation.of(chunk))
        return citations

    def _no_answer(self) -> RegulationAnswer:
        return RegulationAnswer(answer=NO_ANSWER, citations=[], has_answer=False)

    def _refusal(self, chunks: list[RetrievedChunk], *, latency_ms: int) -> AnsweredQuestion:
        """Nothing worth reading was retrieved, so nothing is asked and nothing is spent."""
        return AnsweredQuestion(
            answer=self._no_answer(),
            usage=LLMUsage(
                provider="none",
                model=self._model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                estimated_cost_usd=Decimal(0),
                attempts=0,
            ),
            retrieved=chunks,
        )
