"""The two probes, which answer two different questions (ADR 0020).

- **`/health`, liveness: is the process alive?** No I/O at all. A platform restarts the container
  when it fails, so it must fail only when a restart would help. A liveness probe that checks the
  database restarts a healthy service every time the database hiccups, and loses the reviews in
  flight with it.
- **`/ready`, readiness: can it take a request now?** It checks the corpus store, the cache and
  today's budget, and answers 503 with `Retry-After` when the answer is no. That is a reason to
  send traffic elsewhere or wait, never to restart.

The cache being down does not make the service unready: the cache, the rate limiter and the spend
guard all fail open by design, so it is reported and nothing more.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dependencies import get_engine, get_redis, get_spend_guard
from app.foundation.guardrails.spend import BudgetExhausted, SpendGuard
from app.foundation.persistence.cache import cache_status
from app.foundation.persistence.database import UNAVAILABLE, database_status

router = APIRouter(tags=["probes"])

# How long a client should wait before asking an unready service again, when nothing better is known.
RETRY_AFTER_SECONDS = 30


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    engine: Annotated[AsyncEngine | None, Depends(get_engine)],
    redis: Annotated[Redis | None, Depends(get_redis)],
    spend: Annotated[SpendGuard, Depends(get_spend_guard)],
) -> JSONResponse:
    database = await database_status(engine)
    cache = await cache_status(redis)

    budget, retry_after = "ok", RETRY_AFTER_SECONDS
    try:
        await spend.check()
    except BudgetExhausted as exhausted:
        budget, retry_after = "exhausted", exhausted.retry_after

    is_ready = database != UNAVAILABLE and budget == "ok"
    body = {"status": "ready" if is_ready else "not_ready", "database": database, "cache": cache, "budget": budget}
    if is_ready:
        return JSONResponse(body)
    return JSONResponse(body, status_code=503, headers={"Retry-After": str(retry_after)})
