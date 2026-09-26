"""Where a graph run's state lives between nodes: the project's Postgres, through LangGraph's saver.

The checkpoint tables are LangGraph's, created and migrated by `setup()`, which keeps its own list of
applied migrations. The corpus schema is Alembic's. Copying LangGraph's DDL into an Alembic migration
would pin this service to the library's schema of today and break silently on its next upgrade; the
library owning its tables is the lesser coupling (ADR 0026).

Built lazily, on the first run: the service starts without it, and a database that is not there yet
is a failed run, not a failed start.
"""

import asyncio

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

log = structlog.get_logger()


def psycopg_url(database_url: str) -> str:
    """The service's URL names the asyncpg driver; the checkpointer speaks psycopg."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


class PostgresCheckpoints:
    def __init__(self, database_url: str, *, max_connections: int = 5) -> None:
        self._url = psycopg_url(database_url)
        self._max_connections = max_connections
        self._saver: AsyncPostgresSaver | None = None
        self._lock = asyncio.Lock()

    async def __call__(self) -> BaseCheckpointSaver[str]:
        async with self._lock:
            if self._saver is None:
                pool: AsyncConnectionPool = AsyncConnectionPool(
                    conninfo=self._url,
                    max_size=self._max_connections,
                    open=False,
                    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                )
                await pool.open()
                saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
                await saver.setup()
                self._saver = saver
                log.info("checkpoints.ready", backend="postgres")
        return self._saver


class MemoryCheckpoints:
    """Without a database: the graph still runs, but a run does not survive a restart, and says so."""

    def __init__(self) -> None:
        self._saver = InMemorySaver()
        log.warning("checkpoints.in_memory", reason="no DATABASE_URL: runs do not survive a restart")

    async def __call__(self) -> BaseCheckpointSaver[str]:
        return self._saver
