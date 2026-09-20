"""Connection plumbing for the corpus store. No schema here: the schema belongs to the migrations.

The store is optional on purpose. The listing review of #1 never touches it, so a missing or
unreachable database degrades the service instead of stopping it: `/health` reports what is
going on and the review keeps working. Only the retrieval endpoints, from #22 onwards, will
actually require it.
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

log = structlog.get_logger()

DISABLED = "disabled"
UNAVAILABLE = "unavailable"
OK = "ok"


def create_engine(url: str) -> AsyncEngine:
    # pool_pre_ping: the database outlives no deploy, and a connection recycled by the server
    # should cost one extra round trip, not a failed request.
    return create_async_engine(url, pool_pre_ping=True)


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_connection(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        # A health probe that raises is a health probe nobody can call: every failure, from a
        # refused connection to an unresolvable host, is an answer, not an error.
        log.warning("database.unavailable", exc_info=True)
        return False
    return True


async def database_status(engine: AsyncEngine | None) -> str:
    """`disabled` (not configured), `unavailable` (configured but unreachable) or `ok`."""
    if engine is None:
        return DISABLED
    return OK if await check_connection(engine) else UNAVAILABLE
