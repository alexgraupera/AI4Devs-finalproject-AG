"""The only test in the suite that needs a real database.

It is skipped unless `DATABASE_URL` is exported (`.env` is deliberately not enough: the default
suite stays hermetic and CI needs no services). Run it against a throwaway database, because it
drops the corpus tables on the way down:

    DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental uv run pytest tests/persistence
"""

import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.foundation.persistence.database import create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is not exported: no database to migrate")


def alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


async def migrate(revision: str) -> None:
    # `env.py` drives the async engine with `asyncio.run`, which refuses to start inside the
    # loop of an async test: the migration runs in a thread, exactly as the CLI runs it.
    run = command.downgrade if revision == "base" else command.upgrade
    await asyncio.to_thread(run, alembic_config(), revision)


async def table_names(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: inspect(sync).get_table_names())


@pytest.fixture
async def engine() -> AsyncEngine:
    return create_engine(DATABASE_URL)


async def test_migrations_create_the_corpus_schema_and_undo_it(engine: AsyncEngine) -> None:
    await migrate("head")
    after_upgrade = await table_names(engine)

    await migrate("base")
    after_downgrade = await table_names(engine)

    # Left at head: the next test, and the developer who ran this, find a usable database.
    await migrate("head")

    assert {"documents", "chunks"} <= set(after_upgrade)
    assert {"documents", "chunks"}.isdisjoint(after_downgrade)


async def test_the_vector_extension_is_installed(engine: AsyncEngine) -> None:
    await migrate("head")

    async with engine.connect() as connection:
        installed = await connection.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))

    assert installed.scalar() == 1


async def test_a_block_cannot_be_ingested_twice_into_the_same_document(engine: AsyncEngine) -> None:
    await migrate("head")

    async with engine.begin() as connection:
        document_id = await connection.scalar(
            text(
                "INSERT INTO documents (source_id, title, jurisdiction, doc_type, url, boe_updated_at, corpus_version)"
                " VALUES ('BOE-TEST-1', 'Ley de prueba', 'state', 'consolidated_law', 'https://example.org',"
                " '20260920T000000Z', 'test') RETURNING id"
            )
        )
        chunk = text(
            "INSERT INTO chunks (document_id, block_id, article_title, ordinal, text, char_count, metadata,"
            " content_hash) VALUES (:document_id, 'a36', 'Artículo 36', 0, 'Fianza', 6, '{}'::jsonb, 'hash')"
        )
        await connection.execute(chunk, {"document_id": document_id})

        with pytest.raises(Exception, match="chunks_block_piece_unique"):
            await connection.execute(chunk, {"document_id": document_id})

    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM documents WHERE source_id = 'BOE-TEST-1'"))
