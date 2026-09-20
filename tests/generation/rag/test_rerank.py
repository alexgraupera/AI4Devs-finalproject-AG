from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel

from app.foundation.llm.usage import LLMUsage, StructuredCompletion
from app.generation.rag.rerank import Ranking, Reranker, ScoredChunk
from app.generation.rag.retriever import RetrievedChunk

T = TypeVar("T", bound=BaseModel)

A_USAGE = LLMUsage(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=7_000,
    output_tokens=300,
    latency_ms=2_400,
    estimated_cost_usd=Decimal("0.0086"),
)


def a_chunk(chunk_id: int, *, block_id: str = "a36") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=f"Texto del fragmento {chunk_id}",
        score=0.6,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994",
        article_title=f"Artículo {chunk_id}",
        block_id=block_id,
        jurisdiction="state",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        fecha_vigencia="20190306",
    )


class FakeLLM:
    def __init__(self, ranking: Ranking | None = None, error: Exception | None = None) -> None:
        self.ranking = ranking
        self.error = error
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.calls += 1
        self.prompts.append((system, user))
        if self.error is not None:
            raise self.error
        return StructuredCompletion(output=self.ranking, usage=A_USAGE)  # type: ignore[arg-type]


def ranking(*pairs: tuple[int, int]) -> Ranking:
    return Ranking(ranked=[ScoredChunk(chunk_id=cid, relevance=score) for cid, score in pairs])


def reranker(llm: FakeLLM, top_n: int = 3) -> Reranker:
    return Reranker(llm, top_n=top_n)


async def test_reports_what_the_reordering_cost() -> None:
    llm = FakeLLM(ranking((1, 5), (2, 3)))

    reranked = await reranker(llm).rerank("¿fianza?", [a_chunk(1), a_chunk(2)])

    assert reranked.usage is not None
    assert reranked.usage.input_tokens == 7_000


async def test_a_failure_costs_nothing_and_says_so() -> None:
    llm = FakeLLM(error=RuntimeError("down"))

    reranked = await reranker(llm).rerank("¿fianza?", [a_chunk(1), a_chunk(2)])

    assert reranked.usage is None


async def test_reorders_the_candidates_by_the_scores_the_model_gave() -> None:
    candidates = [a_chunk(1), a_chunk(2), a_chunk(3)]
    llm = FakeLLM(ranking((1, 2), (2, 9), (3, 5)))

    ordered = (await reranker(llm).rerank("¿fianza?", candidates)).chunks

    assert [c.chunk_id for c in ordered] == [2, 3, 1]


async def test_cuts_at_top_n() -> None:
    candidates = [a_chunk(i) for i in range(1, 6)]
    llm = FakeLLM(ranking((1, 1), (2, 2), (3, 3), (4, 4), (5, 5)))

    ordered = (await reranker(llm, top_n=2).rerank("¿fianza?", candidates)).chunks

    assert [c.chunk_id for c in ordered] == [5, 4]


async def test_an_invented_id_is_dropped_as_a_citation_would_be() -> None:
    candidates = [a_chunk(1), a_chunk(2)]
    llm = FakeLLM(ranking((99, 10), (1, 5), (2, 1)))

    ordered = (await reranker(llm).rerank("¿fianza?", candidates)).chunks

    assert [c.chunk_id for c in ordered] == [1, 2]


async def test_a_candidate_the_model_forgot_keeps_its_place_behind_the_ranked_ones() -> None:
    candidates = [a_chunk(1), a_chunk(2), a_chunk(3)]
    llm = FakeLLM(
        ranking(
            (3, 9),
        )
    )

    ordered = (await reranker(llm).rerank("¿fianza?", candidates)).chunks

    assert [c.chunk_id for c in ordered] == [3, 1, 2]


async def test_a_model_failure_returns_the_original_order() -> None:
    candidates = [a_chunk(1), a_chunk(2), a_chunk(3)]
    llm = FakeLLM(error=RuntimeError("provider is down"))

    ordered = (await reranker(llm, top_n=2).rerank("¿fianza?", candidates)).chunks

    assert [c.chunk_id for c in ordered] == [1, 2]


async def test_a_single_candidate_is_not_worth_a_model_call() -> None:
    llm = FakeLLM(ranking((1, 10)))

    ordered = (await reranker(llm).rerank("¿fianza?", [a_chunk(1)])).chunks

    assert llm.calls == 0
    assert [c.chunk_id for c in ordered] == [1]


async def test_nothing_to_rerank_is_not_a_model_call_either() -> None:
    llm = FakeLLM(ranking())

    assert (await reranker(llm).rerank("¿fianza?", [])).chunks == []
    assert llm.calls == 0


async def test_the_candidates_reach_the_prompt_with_their_numbers() -> None:
    llm = FakeLLM(ranking((1, 5), (2, 3)))

    await reranker(llm).rerank("¿cuál es la fianza?", [a_chunk(1), a_chunk(2)])

    _, user = llm.prompts[0]
    assert "[1]" in user
    assert "[2]" in user
    assert "¿cuál es la fianza?" in user
