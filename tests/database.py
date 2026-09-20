"""Databases for the tests, never the one you work with.

The database-backed tests operate on the whole schema, not on their own rows: `embed_pending`
embeds every pending chunk it finds, and `downgrade base` drops the tables outright. Pointed at
a developer's database, that silently destroys the corpus they had just ingested, so each kind
of test gets its own database, created on the fly next to the configured one.

`DATABASE_URL` still decides **whether** these tests run (they skip when it is not exported) and
which server they run on. It is never the database they write to.
"""

import asyncio
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "")

SKIP_REASON = "DATABASE_URL is not exported: no database server to test against"


def database_url(suffix: str) -> str:
    """`postgresql+asyncpg://.../rental` becomes `.../rental_<suffix>`."""
    if not DATABASE_URL:
        return ""
    url = make_url(DATABASE_URL)
    return url.set(database=f"{url.database}_{suffix}").render_as_string(hide_password=False)


def create_database(url: str) -> None:
    asyncio.run(_create_database(url))


def migrate(url: str, revision: str = "head") -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    run = command.downgrade if revision == "base" else command.upgrade
    run(config, revision)


async def _create_database(url: str) -> None:
    name = make_url(url).database
    admin_url: URL = make_url(DATABASE_URL).set(database="postgres")
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            exists = await connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name})
            if not exists:
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin.dispose()
