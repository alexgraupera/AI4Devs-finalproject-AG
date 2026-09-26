"""Who may talk to the service, which endpoints they may use, and how often.

Two independent layers, so exposure needs two mistakes rather than one (ADR 0020):

- **The service token** is a middleware over the whole app: may you talk to this service at all.
  In a real marketplace only the business backend holds it; here, only the Streamlit client does.
- **The API key and the rate limiter** are router dependencies on every business router: which
  endpoints you may use, and how often. A new endpoint under a guarded router is protected by
  being there, not by remembering to protect it.

The probes and the OpenAPI docs are deliberately outside both: a probe that needs a secret is a
probe that stops working the day the secret rotates.

Every comparison is constant-time, and a missing secret gets the same neutral 401 as a wrong one:
telling an attacker which of the two it was is free information.
"""

import hmac
from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.api.errors import error_response
from app.config import Settings, get_settings
from app.dependencies import get_rate_limiter
from app.domain.errors import Unauthorized
from app.foundation.guardrails.rate_limit import RateLimiter

log = structlog.get_logger()

API_KEY_HEADER = "X-API-Key"
SERVICE_TOKEN_HEADER = "X-Service-Token"

# Reachable without the token: the probes a platform calls, and the contract a client reads.
OPEN_PATHS = frozenset({"/health", "/ready", "/docs", "/redoc", "/openapi.json"})

# auto_error=False so a missing key reaches our handler and gets the same neutral answer as a
# wrong one.
_api_key = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def same_secret(presented: str | None, configured: str) -> bool:
    """Constant-time, so the time a comparison takes says nothing about how much of it matched."""
    return presented is not None and hmac.compare_digest(presented.encode(), configured.encode())


class ServiceTokenMiddleware(BaseHTTPMiddleware):
    """Rejects every request without the service token, except the open paths.

    Only installed when a token is configured. Production refuses to start without one (see
    `Settings.missing_for_production`), because an empty token on both sides compares equal.
    """

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        presented = request.headers.get(SERVICE_TOKEN_HEADER)
        if not same_secret(presented, self._token):
            log.info("security.rejected", layer="service_token", reason="missing" if not presented else "wrong")
            response: JSONResponse = error_response("unauthorized", status_code=401)
            return response
        return await call_next(request)


async def require_api_key(
    key: Annotated[str | None, Depends(_api_key)],
    # Injected rather than read directly, so a test can configure a key without reaching into
    # a cache. A dependency that cannot be overridden cannot be tested.
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    configured = settings.api_key
    if not configured:
        # Local development and the tests run without a key. The warning is logged on every
        # request on purpose: an open service in production should be noisy (and production
        # refuses to start without a key anyway).
        log.warning("security.api_key_not_configured")
        return ""

    if not same_secret(key, configured):
        log.info("security.rejected", layer="api_key", reason="missing" if not key else "wrong")
        raise Unauthorized("the API key is missing or wrong")
    return configured


async def enforce_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    key: Annotated[str, Depends(require_api_key)],
) -> None:
    # Keyed by API key when there is one, by client host otherwise: without a key every caller
    # would share one bucket and the first busy one would lock out the rest.
    identity = key or (request.client.host if request.client else "unknown")
    await limiter.check(identity)
