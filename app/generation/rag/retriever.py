"""Finding the articles that answer a question.

Two things this deliberately does not do:

**It does not lower the threshold to find something.** A question the corpus does not cover
returns an empty list, because the alternative is handing the model three irrelevant articles
and letting it write a confident answer from them.

**It does not mix vector spaces.** Only chunks embedded with the model currently configured are
searched: a row left over from another model would be compared in a space where the distance
means nothing.
"""

import time
from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.generation.rag.embeddings import EmbeddingClient

log = structlog.get_logger()

DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.5


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    text: str
    score: float
    law_id: str
    law_title: str
    article_title: str
    block_id: str
    jurisdiction: str
    citation_url: str
    fecha_vigencia: str


class Retriever:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: EmbeddingClient,
        *,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        self._sessions = session_factory
        self._client = client
        self._top_k = top_k
        self._min_score = min_score

    async def search(
        self,
        query: str,
        *,
        k: int | None = None,
        min_score: float | None = None,
        jurisdictions: list[str] | None = None,
        law_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []

        started = time.perf_counter()
        vectors = await self._client.embed([query])
        threshold = self._min_score if min_score is None else min_score

        async with self._sessions() as session:
            rows = await session.execute(
                _SEARCH,
                {
                    "embedding": str(vectors[0]),
                    "model": self._client.model,
                    "k": k or self._top_k,
                    "min_score": threshold,
                    # NULL means "no filter": pushing that into SQL keeps one query instead of
                    # four assembled by string concatenation.
                    "jurisdictions": jurisdictions or None,
                    "law_ids": law_ids or None,
                },
            )
            results = [
                RetrievedChunk(
                    chunk_id=row.id,
                    text=row.text,
                    score=float(row.score),
                    law_id=row.source_id,
                    law_title=row.law_title,
                    article_title=row.article_title,
                    block_id=row.block_id,
                    jurisdiction=row.jurisdiction,
                    citation_url=row.citation_url or "",
                    fecha_vigencia=row.fecha_vigencia or "",
                )
                for row in rows
            ]

        log.info(
            "retrieval.completed",
            results=len(results),
            top_score=results[0].score if results else None,
            min_score=threshold,
            model=self._client.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return results


# Cosine distance is 0 (identical) to 2 (opposite), so the score is 1 - distance: a number that
# grows with relevance, which is what a threshold should be read against.
_SEARCH = text("""
    SELECT
        c.id,
        c.text,
        c.article_title,
        c.block_id,
        c.metadata ->> 'citation_url' AS citation_url,
        c.metadata ->> 'fecha_vigencia' AS fecha_vigencia,
        d.source_id,
        d.title AS law_title,
        d.jurisdiction,
        1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.embedding IS NOT NULL
      AND c.embedding_model = :model
      -- Cast explicitly: asyncpg cannot infer the type of a parameter that is NULL here and an
      -- array there, and answers "could not determine data type" instead of guessing.
      AND (CAST(:jurisdictions AS text[]) IS NULL OR d.jurisdiction = ANY(CAST(:jurisdictions AS text[])))
      AND (CAST(:law_ids AS text[]) IS NULL OR d.source_id = ANY(CAST(:law_ids AS text[])))
      AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :min_score
    ORDER BY c.embedding <=> CAST(:embedding AS vector)
    LIMIT :k
""")
