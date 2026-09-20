from decimal import Decimal
from typing import TypeVar

import pytest
from pydantic import BaseModel

from app.domain.regulation_qa_service import NO_ANSWER, RegulationQAService
from app.domain.schemas.regulation_answer import AnswerCandidate, RegulationQuestion
from app.foundation.guardrails.input import InputGuardrailViolation
from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.rag.retriever import RetrievedChunk

T = TypeVar("T", bound=BaseModel)

A_USAGE = LLMUsage(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=2_000,
    output_tokens=200,
    latency_ms=900,
    estimated_cost_usd=Decimal("0.0030"),
)

A_QUESTION = RegulationQuestion(question="¿Cuál es la fianza legal en un alquiler de vivienda?")


def a_chunk(chunk_id: int = 36, *, block_id: str = "a36", score: float = 0.72) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="Artículo 36. Fianza. Una mensualidad de renta en el arrendamiento de viviendas.",
        score=score,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994, de Arrendamientos Urbanos",
        article_title="Artículo 36",
        block_id=block_id,
        jurisdiction="state",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        fecha_vigencia="20190306",
    )


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self.chunks = [a_chunk()] if chunks is None else chunks
        self.calls: list[dict[str, object]] = []

    async def search(self, query: str, **kwargs: object) -> list[RetrievedChunk]:
        self.calls.append({"query": query, **kwargs})
        return self.chunks


class FakeLLM:
    def __init__(self, candidate: AnswerCandidate) -> None:
        self.candidate = candidate
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.calls += 1
        self.prompts.append((system, user))
        return StructuredCompletion(output=self.candidate, usage=A_USAGE)  # type: ignore[arg-type]


def a_candidate(
    *, has_answer: bool = True, answer: str = "La fianza es de una mensualidad.", cited: list[int] | None = None
) -> AnswerCandidate:
    return AnswerCandidate(
        has_answer=has_answer,
        answer=answer,
        cited_chunk_ids=[36] if cited is None else cited,
    )


def service(llm: FakeLLM, retriever: FakeRetriever) -> RegulationQAService:
    return RegulationQAService(llm=llm, retriever=retriever, model="claude-haiku-4-5")  # type: ignore[arg-type]


async def test_answers_from_the_retrieved_articles_and_cites_them() -> None:
    answered = await service(FakeLLM(a_candidate()), FakeRetriever()).ask(A_QUESTION)

    assert answered.answer.has_answer
    assert answered.answer.answer == "La fianza es de una mensualidad."
    assert [c.article for c in answered.answer.citations] == ["Artículo 36"]
    assert answered.answer.citations[0].url.endswith("#a36")


async def test_the_citation_is_built_from_the_retrieved_chunk_not_from_the_model() -> None:
    # The model only ever returns numbers: the law, the article and the URL come from retrieval.
    answered = await service(FakeLLM(a_candidate()), FakeRetriever()).ask(A_QUESTION)

    citation = answered.answer.citations[0]
    assert citation.law_id == "BOE-A-1994-26003"
    assert citation.chunk_id == 36


async def test_drops_a_citation_the_retrieval_never_returned() -> None:
    llm = FakeLLM(a_candidate(cited=[36, 999]))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert [c.chunk_id for c in answered.answer.citations] == [36]
    assert answered.answer.has_answer


async def test_an_answer_left_with_no_valid_citation_becomes_a_refusal() -> None:
    # Everything it claimed to cite was invented, so nothing supports the answer.
    llm = FakeLLM(a_candidate(cited=[999]))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert not answered.answer.has_answer
    assert answered.answer.answer == NO_ANSWER
    assert answered.answer.citations == []


async def test_repeated_citations_are_reported_once() -> None:
    llm = FakeLLM(a_candidate(cited=[36, 36]))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert len(answered.answer.citations) == 1


async def test_nothing_retrieved_means_no_call_to_the_model() -> None:
    llm = FakeLLM(a_candidate())

    answered = await service(llm, FakeRetriever(chunks=[])).ask(RegulationQuestion(question="¿Qué tiempo hará mañana?"))

    assert llm.calls == 0
    assert not answered.answer.has_answer
    assert answered.answer.answer == NO_ANSWER
    assert answered.usage.input_tokens == 0
    assert answered.usage.estimated_cost_usd == Decimal(0)


async def test_a_model_that_says_it_cannot_answer_is_believed() -> None:
    llm = FakeLLM(a_candidate(has_answer=False, answer="", cited=[]))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert not answered.answer.has_answer
    assert answered.answer.answer == NO_ANSWER


async def test_an_empty_answer_with_citations_is_still_a_refusal() -> None:
    llm = FakeLLM(a_candidate(answer="   "))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert not answered.answer.has_answer


async def test_the_retrieved_chunks_travel_with_the_answer_for_inspection() -> None:
    answered = await service(FakeLLM(a_candidate()), FakeRetriever()).ask(A_QUESTION)

    assert [chunk.chunk_id for chunk in answered.retrieved] == [36]


async def test_the_context_reaches_the_prompt_with_its_numbers() -> None:
    llm = FakeLLM(a_candidate())

    await service(llm, FakeRetriever()).ask(A_QUESTION)

    _, user = llm.prompts[0]
    assert "[36]" in user
    assert "¿Cuál es la fianza legal en un alquiler de vivienda?" in user


async def test_the_jurisdiction_filter_reaches_the_retriever() -> None:
    retriever = FakeRetriever()

    await service(FakeLLM(a_candidate()), retriever).ask(
        RegulationQuestion(question="¿Qué hay que informar en Cataluña?", jurisdictions=["catalonia"])
    )

    assert retriever.calls[0]["jurisdictions"] == ["catalonia"]


async def test_an_empty_question_is_rejected_before_anything_is_searched() -> None:
    retriever = FakeRetriever()
    llm = FakeLLM(a_candidate())

    with pytest.raises(InputGuardrailViolation):
        await service(llm, retriever).ask(RegulationQuestion(question="   "))

    assert retriever.calls == []
    assert llm.calls == 0


async def test_strips_the_fragment_numbers_the_model_copies_into_the_prose() -> None:
    # The regression of #34: "[38]" in the answer means nothing to the person reading it.
    llm = FakeLLM(a_candidate(answer="La fianza es de una mensualidad [36]. Y de dos en locales [36]."))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert answered.answer.answer == "La fianza es de una mensualidad. Y de dos en locales."


async def test_leaves_an_answer_without_markers_untouched() -> None:
    clean = "Según el artículo 36 de la LAU, la fianza es de una mensualidad."
    llm = FakeLLM(a_candidate(answer=clean))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert answered.answer.answer == clean


async def test_an_answer_that_is_only_a_marker_is_not_an_answer() -> None:
    llm = FakeLLM(a_candidate(answer="[36]"))

    answered = await service(llm, FakeRetriever()).ask(A_QUESTION)

    assert not answered.answer.has_answer


async def test_a_refusal_says_what_the_corpus_does_cover() -> None:
    # A refusal that only says "not found" is a dead end: someone asking about rental income tax
    # cannot tell whether they phrased it badly or asked outside the four indexed laws.
    answered = await service(FakeLLM(a_candidate()), FakeRetriever(chunks=[])).ask(
        RegulationQuestion(question="¿Debo declarar en la renta el alquiler?")
    )

    assert "Arrendamientos Urbanos" in answered.answer.answer
    assert "fiscalidad" in answered.answer.answer
