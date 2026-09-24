"""Turning chunks into vectors, and keeping track of which model made them.

Two rules hold this together:

**A vector knows which model made it.** `embedding_model` is stored per row, so switching model
re-embeds instead of silently mixing two vector spaces in one index. That failure does not raise:
it just returns nonsense.

**Re-embedding only pays for what changed.** A chunk whose text did not move keeps its vector,
which is what makes a routine `make ingest` cost nothing.
"""

import time
from dataclasses import dataclass
from typing import Protocol

import litellm
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = structlog.get_logger()

DEFAULT_MODEL = "openai/text-embedding-3-large"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BATCH_SIZE = 100


@dataclass(frozen=True)
class EmbeddingReport:
    model: str
    embedded: int = 0
    already_current: int = 0
    tokens: int = 0
    latency_ms: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        return self.tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS.get(self.model, 0.0)


# USD per million tokens, from https://developers.openai.com/api/docs/pricing on 2026-09-20.
# Kept here rather than in the chat pricing table: embeddings have no output tokens, so the
# (input, output) shape of that table would be a lie.
PRICE_PER_MILLION_TOKENS: dict[str, float] = {
    "openai/text-embedding-3-small": 0.02,
    "openai/text-embedding-3-large": 0.13,
}


class EmbeddingClient(Protocol):
    """What the retrieval and the indexing need: text in, vectors out, and the model's name."""

    model: str
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LiteLLMEmbeddings:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.model = model
        self.dimensions = dimensions
        self._batch_size = batch_size
        self.tokens = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = await litellm.aembedding(model=self.model, input=batch, dimensions=self.dimensions)
            vectors.extend(item["embedding"] for item in response.data)
            self.tokens += int(getattr(response.usage, "prompt_tokens", 0) or 0)
        return vectors


async def embed_pending(
    session_factory: async_sessionmaker[AsyncSession],
    client: EmbeddingClient,
    *,
    force: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EmbeddingReport:
    started = time.perf_counter()

    async with session_factory() as session:
        pending = await _pending_chunks(session, client.model, force=force)
        current = await _current_count(session, client.model) if not force else 0

    embedded = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        vectors = await client.embed([row.text for row in batch])
        if len(vectors) != len(batch):
            raise RuntimeError(f"asked for {len(batch)} embeddings and got {len(vectors)}")

        # Written per batch: a failure halfway leaves the finished batches stored and the rest
        # pending, so re-running resumes instead of starting over.
        async with session_factory() as session, session.begin():
            for row, vector in zip(batch, vectors, strict=True):
                await session.execute(
                    text("""
                        UPDATE chunks
                        SET embedding = :embedding, embedding_model = :model, embedded_at = now()
                        WHERE id = :id
                    """),
                    {"id": row.id, "embedding": str(vector), "model": client.model},
                )
        embedded += len(batch)
        log.info("embeddings.batch", model=client.model, embedded=embedded, pending=len(pending))

    report = EmbeddingReport(
        model=client.model,
        embedded=embedded,
        already_current=current,
        tokens=getattr(client, "tokens", 0),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    log.info(
        "embeddings.completed",
        model=report.model,
        embedded=report.embedded,
        already_current=report.already_current,
        tokens=report.tokens,
        estimated_cost_usd=report.estimated_cost_usd,
        latency_ms=report.latency_ms,
    )
    return report


async def _pending_chunks(session: AsyncSession, model: str, *, force: bool) -> list:  # type: ignore[type-arg]
    # A chunk needs embedding when it has no vector, or when its vector came from another model.
    # `force` re-embeds everything, which is how a model is re-evaluated without clearing rows.
    condition = "" if force else "WHERE embedding IS NULL OR embedding_model IS DISTINCT FROM :model"
    rows = await session.execute(text(f"SELECT id, text FROM chunks {condition} ORDER BY id"), {"model": model})
    return list(rows)


async def _current_count(session: AsyncSession, model: str) -> int:
    count = await session.scalar(
        text("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL AND embedding_model = :model"),
        {"model": model},
    )
    return int(count or 0)
