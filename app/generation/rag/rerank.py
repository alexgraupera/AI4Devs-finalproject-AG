"""Reordering the candidates with a model that reads them, instead of a vector that summarises them.

An embedding compares a question to an average of an article's meaning. A reranker reads both and
judges. That is strictly more informed, and strictly more expensive: one model call per query,
over a context of twenty articles.

Whether it pays on this corpus is a question for the benchmark. Chunks here are whole articles,
so the candidates are already coarse and there may be little left to reorder, which is why this
is the technique most likely to be deleted rather than kept.

A failure returns the candidates untouched: reranking improves an order, it does not own it.
"""

from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_regulations_rerank_prompt
from app.generation.rag.retriever import RetrievedChunk

log = structlog.get_logger()

PROMPT_VERSION = "v1"
DEFAULT_TOP_N = 5


class ScoredChunk(BaseModel):
    chunk_id: int = Field(description="El número del fragmento")
    relevance: int = Field(ge=0, le=10, description="0 si no responde nada de la pregunta, 10 si la responde entera")


class Ranking(BaseModel):
    ranked: list[ScoredChunk] = Field(description="Los fragmentos con su relevancia, de mayor a menor")


@dataclass(frozen=True)
class Reranked:
    """The new order, and what it cost. Both travel together, as a review's usage does."""

    chunks: list[RetrievedChunk]
    usage: LLMUsage | None = None


class Reranker:
    def __init__(self, llm: StructuredLLM, *, top_n: int = DEFAULT_TOP_N, prompt_version: str = PROMPT_VERSION) -> None:
        self._llm = llm
        self._top_n = top_n
        self._prompt_version = prompt_version

    async def rerank(self, query: str, candidates: list[RetrievedChunk]) -> Reranked:
        if len(candidates) <= 1:
            return Reranked(chunks=candidates[: self._top_n])

        numbered = "\n\n".join(
            f"[{c.chunk_id}] {c.article_title} · {c.law_title}\n{c.text[:1_200]}" for c in candidates
        )
        system, user = render_regulations_rerank_prompt(query, numbered, version=self._prompt_version)

        try:
            completion = await self._llm.complete_structured(system=system, user=user, schema=Ranking)
        except Exception:
            log.warning("rerank.failed", exc_info=True)
            return Reranked(chunks=candidates[: self._top_n])

        by_id = {chunk.chunk_id: chunk for chunk in candidates}
        ordered = [
            by_id[scored.chunk_id]
            for scored in sorted(completion.output.ranked, key=lambda s: s.relevance, reverse=True)
            # A model that invents an id has not reordered anything: it is dropped, as citations are.
            if scored.chunk_id in by_id
        ]
        # Anything the model forgot keeps its original order behind what it did rank.
        ordered += [chunk for chunk in candidates if chunk not in ordered]

        log.info(
            "rerank.completed",
            candidates=len(candidates),
            ranked=len(completion.output.ranked),
            input_tokens=completion.usage.input_tokens,
            latency_ms=completion.usage.latency_ms,
        )
        return Reranked(chunks=ordered[: self._top_n], usage=completion.usage)
