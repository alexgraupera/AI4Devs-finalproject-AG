"""Sharing one HTTP client across an ingestion run, without closing someone else's.

Every fetch here takes an optional client: the ingestion passes one and reuses its connections,
a caller asking for a single law gets a throwaway. Only the client we created is closed, because
closing a borrowed one breaks the caller's next request.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def borrowed_or_own(client: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient() as owned:
        yield owned
