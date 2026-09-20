"""Retrieval, against a real pgvector index.

Vectors here are hand-made rather than produced by a model: the question these tests answer is
what the retriever does with a given similarity, not whether an embedding model is any good.
That is what the benchmark of #24 is for.
"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.foundation.persistence.database import create_engine, session_factory
from app.generation.rag.retriever import Retriever
from tests.conftest import CORPUS_TEST_URL
from tests.database import DATABASE_URL, SKIP_REASON

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason=SKIP_REASON)

DIMENSIONS = 1536
STATE_LAW = "BOE-TEST-RETRIEVAL-STATE"
REGIONAL_LAW = "BOE-TEST-RETRIEVAL-CATALONIA"
SOURCES = [STATE_LAW, REGIONAL_LAW]


def vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second] + [0.0] * (DIMENSIONS - 2)


class FixedEmbeddings:
    """Embeds the query as whatever vector the test needs."""

    model = "fake/model"
    dimensions = DIMENSIONS

    def __init__(self, query_vector: list[float]) -> None:
        self._vector = query_vector
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vector for _ in texts]


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(CORPUS_TEST_URL)
    factory = session_factory(engine)
    await clean(factory)
    await seed(factory)
    yield factory
    await clean(factory)
    await engine.dispose()


async def clean(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as session, session.begin():
        await session.execute(text("DELETE FROM documents WHERE source_id = ANY(:ids)"), {"ids": SOURCES})


async def seed(sessions: async_sessionmaker[AsyncSession]) -> None:
    rows = [
        (STATE_LAW, "state", "a36", "Artículo 36", "Fianza de una mensualidad", vector(1.0), "fake/model"),
        (STATE_LAW, "state", "a20", "Artículo 20", "Gastos de gestión inmobiliaria", vector(0.0, 1.0), "fake/model"),
        (
            REGIONAL_LAW,
            "catalonia",
            "a61",
            "Artículo 61",
            "Oferta para el arrendamiento",
            vector(0.6, 0.8),
            "fake/model",
        ),
        # Left over from another model: it must never be compared against the current space.
        (STATE_LAW, "state", "a99", "Artículo 99", "Vector de otro modelo", vector(1.0), "fake/other-model"),
    ]
    async with sessions() as session, session.begin():
        documents = {}
        for source_id, jurisdiction in [(STATE_LAW, "state"), (REGIONAL_LAW, "catalonia")]:
            documents[source_id] = await session.scalar(
                text("""
                    INSERT INTO documents (source_id, title, jurisdiction, doc_type, url, boe_updated_at,
                                           corpus_version)
                    VALUES (:s, :title, :j, 'consolidated_law', 'https://example.org', '2026', 'test')
                    RETURNING id
                """),
                {"s": source_id, "title": f"Ley {source_id}", "j": jurisdiction},
            )
        for source_id, _, block_id, title, body, embedding, model in rows:
            await session.execute(
                text("""
                    INSERT INTO chunks (document_id, block_id, article_title, ordinal, text, char_count,
                                        metadata, content_hash, embedding, embedding_model, embedded_at)
                    VALUES (:d, :block, :title, 0, :text, :len,
                            CAST(:metadata AS jsonb), :hash, CAST(:embedding AS vector), :model, now())
                """),
                {
                    "d": documents[source_id],
                    "block": block_id,
                    "title": title,
                    "text": body,
                    "len": len(body),
                    "metadata": f'{{"citation_url": "https://www.boe.es/buscar/act.php?id={source_id}#{block_id}"}}',
                    "hash": block_id,
                    "embedding": str(embedding),
                    "model": model,
                },
            )


def retriever(sessions: async_sessionmaker[AsyncSession], query_vector: list[float], **kwargs: float) -> Retriever:
    return Retriever(sessions, FixedEmbeddings(query_vector), **kwargs)  # type: ignore[arg-type]


async def test_returns_the_closest_article_first(sessions: async_sessionmaker[AsyncSession]) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("¿cuál es la fianza?")

    assert results[0].article_title == "Artículo 36"
    assert results[0].score > results[-1].score


async def test_carries_what_a_citation_needs(sessions: async_sessionmaker[AsyncSession]) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("fianza")

    first = results[0]
    assert first.law_id == STATE_LAW
    assert first.block_id == "a36"
    assert first.citation_url.endswith("#a36")
    assert first.jurisdiction == "state"


async def test_drops_what_falls_below_the_threshold(sessions: async_sessionmaker[AsyncSession]) -> None:
    # Against the query vector: a36 scores 1.0, a61 scores 0.6 and a20 scores 0.
    loose = await retriever(sessions, vector(1.0), min_score=0.3).search("fianza")
    strict = await retriever(sessions, vector(1.0), min_score=0.95).search("fianza")

    assert [r.block_id for r in loose] == ["a36", "a61"]
    assert [r.block_id for r in strict] == ["a36"]


async def test_an_unanswerable_question_returns_nothing_rather_than_the_least_bad_match(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # Orthogonal to everything stored: a cosine score of 0 against every article.
    orthogonal = [0.0, 0.0, 1.0] + [0.0] * (DIMENSIONS - 3)

    results = await retriever(sessions, orthogonal, min_score=0.3).search("¿qué tiempo hará mañana?")

    assert results == []


async def test_limits_the_results_to_k(sessions: async_sessionmaker[AsyncSession]) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("fianza", k=2)

    assert len(results) == 2


async def test_filters_by_jurisdiction(sessions: async_sessionmaker[AsyncSession]) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("oferta", jurisdictions=["catalonia"])

    assert {r.law_id for r in results} == {REGIONAL_LAW}


async def test_filters_by_law(sessions: async_sessionmaker[AsyncSession]) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("fianza", law_ids=[STATE_LAW])

    assert {r.law_id for r in results} == {STATE_LAW}


async def test_never_compares_against_vectors_from_another_model(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    results = await retriever(sessions, vector(1.0), min_score=0.0).search("fianza")

    assert "a99" not in {r.block_id for r in results}


async def test_an_empty_question_does_not_reach_the_provider(sessions: async_sessionmaker[AsyncSession]) -> None:
    client = FixedEmbeddings(vector(1.0))

    results = await Retriever(sessions, client, min_score=0.0).search("   ")

    assert results == []
    assert client.calls == 0
