"""Who may ask the corpus, and how often.

The retrieval endpoints are a data service, not a public one: they expose a corpus that costs
money to build and money to query. Both guards live here as router dependencies, so a new
endpoint under `/regulations` is protected by being there, not by remembering to protect it.

`/health` is deliberately outside: a probe that needs a secret is a probe that stops working
the day the secret rotates.
"""

from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.dependencies import get_rate_limiter
from app.domain.errors import Unauthorized
from app.foundation.guardrails.rate_limit import RateLimiter

log = structlog.get_logger()

API_KEY_HEADER = "X-API-Key"

# auto_error=False so a missing key reaches our handler and gets the same neutral answer as a
# wrong one: telling an attacker which of the two it was is free information.
_api_key = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


async def require_api_key(
    key: Annotated[str | None, Depends(_api_key)],
    # Injected rather than read directly, so a test can configure a key without reaching into
    # a cache. A dependency that cannot be overridden cannot be tested.
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    configured = settings.rag_api_key
    if not configured:
        # Local development and the tests run without a key. The warning is logged on every
        # request on purpose: an unprotected corpus in production should be noisy.
        log.warning("security.api_key_not_configured")
        return ""

    if key != configured:
        log.info("security.rejected", reason="missing" if not key else "wrong")
        raise Unauthorized("the API key is missing or wrong")
    return key


async def enforce_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    key: Annotated[str, Depends(require_api_key)],
) -> None:
    # Keyed by API key when there is one, by client host otherwise: without a key every caller
    # would share one bucket and the first busy one would lock out the rest.
    identity = key or (request.client.host if request.client else "unknown")
    await limiter.check(identity)
