"""Embedding decisions, tested with the provider faked and the database real."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.foundation.persistence.database import create_engine, session_factory
from app.generation.rag.embeddings import EmbeddingReport, embed_pending
from tests.conftest import CORPUS_TEST_URL
from tests.database import DATABASE_URL, SKIP_REASON

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason=SKIP_REASON)

A_SOURCE = "BOE-TEST-EMBEDDINGS"


class FakeEmbeddings:
    """Returns a deterministic vector per text, and records what it was asked to embed."""

    def __init__(self, model: str = "fake/model", dimensions: int = 1536, error: Exception | None = None) -> None:
        self.model = model
        self.dimensions = dimensions
        self.batches: list[list[str]] = []
        self.tokens = 0
        self._error = error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._error is not None:
            raise self._error
        self.batches.append(texts)
        self.tokens += sum(len(t) // 4 for t in texts)
        return [[float(len(t) % 10)] + [0.0] * (self.dimensions - 1) for t in texts]

    @property
    def embedded_texts(self) -> list[str]:
        return [text for batch in self.batches for text in batch]


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(CORPUS_TEST_URL)
    factory = session_factory(engine)
    async with factory() as session, session.begin():
        await session.execute(text("DELETE FROM documents WHERE source_id = :s"), {"s": A_SOURCE})
    yield factory
    async with factory() as session, session.begin():
        await session.execute(text("DELETE FROM documents WHERE source_id = :s"), {"s": A_SOURCE})
    await engine.dispose()


async def given_chunks(sessions: async_sessionmaker[AsyncSession], texts: list[str]) -> None:
    async with sessions() as session, session.begin():
        document_id = await session.scalar(
            text("""
                INSERT INTO documents (source_id, title, jurisdiction, doc_type, url, boe_updated_at, corpus_version)
                VALUES (:s, 'Ley de prueba', 'state', 'consolidated_law', 'https://example.org', '2026', 'test')
                RETURNING id
            """),
            {"s": A_SOURCE},
        )
        for ordinal, body in enumerate(texts):
            await session.execute(
                text("""
                    INSERT INTO chunks (document_id, block_id, article_title, ordinal, text, char_count,
                                        metadata, content_hash)
                    VALUES (:d, :block, 'Artículo', 0, :text, :len, '{}'::jsonb, :hash)
                """),
                {"d": document_id, "block": f"a{ordinal}", "text": body, "len": len(body), "hash": f"h{ordinal}"},
            )


async def stored(sessions: async_sessionmaker[AsyncSession], column: str = "embedding_model") -> list[str | None]:
    async with sessions() as session:
        rows = await session.execute(
            text(
                f"SELECT {column} AS value FROM chunks c JOIN documents d ON d.id = c.document_id"
                " WHERE d.source_id = :s ORDER BY c.id"
            ),
            {"s": A_SOURCE},
        )
        return [row.value for row in rows]


async def test_embeds_the_chunks_that_have_no_vector(sessions: async_sessionmaker[AsyncSession]) -> None:
    await given_chunks(sessions, ["Fianza", "Gastos"])
    client = FakeEmbeddings()

    report = await embed_pending(sessions, client)

    assert report.embedded == 2
    assert sorted(client.embedded_texts) == ["Fianza", "Gastos"]
    assert await stored(sessions) == ["fake/model", "fake/model"]


async def test_a_second_run_embeds_nothing(sessions: async_sessionmaker[AsyncSession]) -> None:
    await given_chunks(sessions, ["Fianza"])
    await embed_pending(sessions, FakeEmbeddings())

    client = FakeEmbeddings()
    report = await embed_pending(sessions, client)

    assert report.embedded == 0
    assert client.embedded_texts == []
    assert report.already_current >= 1


async def test_changing_the_model_re_embeds_instead_of_mixing_vector_spaces(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await given_chunks(sessions, ["Fianza"])
    await embed_pending(sessions, FakeEmbeddings(model="fake/small"))

    client = FakeEmbeddings(model="fake/large")
    report = await embed_pending(sessions, client)

    assert report.embedded == 1
    assert await stored(sessions) == ["fake/large"]


async def test_force_re_embeds_what_is_already_current(sessions: async_sessionmaker[AsyncSession]) -> None:
    await given_chunks(sessions, ["Fianza"])
    await embed_pending(sessions, FakeEmbeddings())

    client = FakeEmbeddings()
    report = await embed_pending(sessions, client, force=True)

    assert report.embedded == 1
    assert client.embedded_texts == ["Fianza"]


async def test_embeds_in_batches_of_the_configured_size(sessions: async_sessionmaker[AsyncSession]) -> None:
    await given_chunks(sessions, [f"Artículo {i}" for i in range(5)])
    client = FakeEmbeddings()

    await embed_pending(sessions, client, batch_size=2)

    assert [len(batch) for batch in client.batches] == [2, 2, 1]


async def test_a_provider_failure_leaves_no_half_written_vectors(sessions: async_sessionmaker[AsyncSession]) -> None:
    await given_chunks(sessions, ["Fianza", "Gastos"])

    with pytest.raises(RuntimeError, match="provider is down"):
        await embed_pending(sessions, FakeEmbeddings(error=RuntimeError("provider is down")))

    assert await stored(sessions) == [None, None]


async def test_a_provider_returning_the_wrong_number_of_vectors_is_refused(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    class Short(FakeEmbeddings):
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return (await super().embed(texts))[:-1]

    await given_chunks(sessions, ["Fianza", "Gastos"])

    with pytest.raises(RuntimeError, match="asked for 2 embeddings"):
        await embed_pending(sessions, Short())


def test_the_cost_is_estimated_from_the_published_price() -> None:
    report = EmbeddingReport(model="openai/text-embedding-3-small", embedded=380, tokens=154_287)

    assert round(report.estimated_cost_usd, 4) == 0.0031


def test_an_unknown_model_costs_nothing_rather_than_guessing() -> None:
    assert EmbeddingReport(model="fake/model", tokens=1_000_000).estimated_cost_usd == 0.0
