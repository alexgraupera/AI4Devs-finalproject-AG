"""Idempotency is the claim of this phase, so it is tested against a real PostgreSQL.

Skipped unless `DATABASE_URL` is exported, like the migration tests:

    DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental uv run pytest tests/ingestion
"""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.foundation.persistence.database import create_engine, session_factory
from app.ingestion.chunking import Chunk, content_hash
from app.ingestion.repository import replace_chunks, stored_versions, upsert_document
from app.ingestion.sources import DocType, Jurisdiction, Source

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is not exported: no database to write to")

A_SOURCE = Source(
    source_id="BOE-TEST-CORPUS",
    title="Ley de prueba",
    jurisdiction=Jurisdiction.STATE,
    doc_type=DocType.CONSOLIDATED_LAW,
)


def a_chunk(block_id: str = "a36", ordinal: int = 0, body: str = "Fianza de una mensualidad") -> Chunk:
    return Chunk(
        block_id=block_id,
        article_title="Artículo 36",
        ordinal=ordinal,
        text=body,
        char_count=len(body),
        metadata={"citation_url": "https://www.boe.es/buscar/act.php?id=BOE-TEST-CORPUS#a36"},
        content_hash=content_hash(body),
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_engine(DATABASE_URL)
    async with session_factory(engine)() as opened:
        yield opened
        await opened.rollback()
        async with opened.begin():
            await opened.execute(
                text("DELETE FROM documents WHERE source_id = :source_id"), {"source_id": A_SOURCE.source_id}
            )
    await engine.dispose()


async def a_document(session: AsyncSession, *, updated_at: str = "20260430T073359Z") -> int:
    async with session.begin():
        return await upsert_document(
            session,
            A_SOURCE,
            title=A_SOURCE.title,
            url="https://www.boe.es/buscar/act.php?id=BOE-TEST-CORPUS",
            boe_updated_at=updated_at,
            corpus_version="test",
        )


async def chunk_count(session: AsyncSession, document_id: int) -> int:
    count = await session.scalar(
        text("SELECT count(*) FROM chunks WHERE document_id = :document_id"), {"document_id": document_id}
    )
    return int(count or 0)


async def test_writing_the_same_corpus_twice_changes_nothing(session: AsyncSession) -> None:
    document_id = await a_document(session)
    chunks = [a_chunk("a36"), a_chunk("a20", body="Gastos de gestión")]

    async with session.begin():
        first = await replace_chunks(session, document_id, chunks)
    async with session.begin():
        second = await replace_chunks(session, document_id, chunks)

    assert (first.written, first.updated, first.unchanged) == (2, 0, 0)
    assert (second.written, second.updated, second.unchanged) == (0, 0, 2)
    assert await chunk_count(session, document_id) == 2


async def test_a_reformed_article_is_updated_in_place(session: AsyncSession) -> None:
    document_id = await a_document(session)
    async with session.begin():
        await replace_chunks(session, document_id, [a_chunk("a36")])

    async with session.begin():
        diff = await replace_chunks(session, document_id, [a_chunk("a36", body="Fianza de dos mensualidades")])

    assert (diff.written, diff.updated, diff.deleted) == (0, 1, 0)
    assert await chunk_count(session, document_id) == 1
    stored = await session.scalar(
        text("SELECT text FROM chunks WHERE document_id = :document_id"), {"document_id": document_id}
    )
    assert stored == "Fianza de dos mensualidades"


async def test_an_article_that_disappeared_from_the_source_leaves_the_corpus(session: AsyncSession) -> None:
    document_id = await a_document(session)
    async with session.begin():
        await replace_chunks(session, document_id, [a_chunk("a36"), a_chunk("a20", body="Gastos")])

    async with session.begin():
        diff = await replace_chunks(session, document_id, [a_chunk("a36")])

    assert diff.deleted == 1
    assert await chunk_count(session, document_id) == 1


async def test_the_pieces_of_a_split_article_live_side_by_side(session: AsyncSession) -> None:
    document_id = await a_document(session)

    async with session.begin():
        diff = await replace_chunks(session, document_id, [a_chunk("a36", 0), a_chunk("a36", 1, body="Continuación")])

    assert diff.written == 2
    assert await chunk_count(session, document_id) == 2


async def test_reingesting_a_source_keeps_one_document(session: AsyncSession) -> None:
    first = await a_document(session, updated_at="20260430T073359Z")
    second = await a_document(session, updated_at="20261001T000000Z")

    assert first == second
    assert await stored_versions(session) == {**await stored_versions(session), A_SOURCE.source_id: "20261001T000000Z"}


async def test_the_stored_versions_are_what_the_skip_decision_reads(session: AsyncSession) -> None:
    await a_document(session, updated_at="20260430T073359Z")

    assert (await stored_versions(session))[A_SOURCE.source_id] == "20260430T073359Z"
