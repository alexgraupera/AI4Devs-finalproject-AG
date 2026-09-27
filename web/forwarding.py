"""Which API calls the marketplace may make, and how they are forwarded with the credentials.

The browser never holds the service token or the API key (ADR 0020): it calls this server, which
adds both and forwards the call. Only the calls the frontend actually makes are forwarded, listed
here one by one; anything else under `/api` is a 404 that never reaches the API. The list grows
with the frontend, one endpoint at a time, never with a wildcard.
"""

import re
from typing import Any

import httpx
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.config import Settings

log = structlog.get_logger()

# A paused run's id (a UUID). Letters, digits and hyphens only: an id is one path segment, and an
# encoded "../" in it must never turn the forwarded path into another endpoint.
RUN_ID = r"[A-Za-z0-9-]{1,64}"

# (method, path pattern), matched against the whole path, as the server decoded it.
ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POST", re.compile(r"/api/v1/regulations/ask")),
    ("POST", re.compile(r"/api/v1/feedback")),
    ("POST", re.compile(r"/api/v1/listings/review")),
    ("POST", re.compile(r"/api/v1/listings/agent-review")),
    ("GET", re.compile(rf"/api/v1/listings/agent-review/{RUN_ID}")),
    ("POST", re.compile(rf"/api/v1/listings/agent-review/{RUN_ID}/resume")),
)

# An agent review runs for up to 90 s in the API, and a sleeping free-tier API takes up to a
# minute to wake before that. Giving up earlier would call a working service unreachable.
FORWARD_TIMEOUT_SECONDS = 180
WAKE_TIMEOUT_SECONDS = 90

UNREACHABLE = "No se ha podido contactar con el servicio. Inténtalo de nuevo."
NOT_FOUND = "Esta ruta no existe."

# What the API answers that the browser needs back, besides the body.
PASSED_BACK_HEADERS = ("content-type", "retry-after", "x-request-id")


def is_allowed(method: str, path: str) -> bool:
    return any(method == allowed and pattern.fullmatch(path) for allowed, pattern in ALLOWED)


def error(code: str, message: str, status_code: int) -> JSONResponse:
    """The API's own error shape, so the frontend reads one kind of error whoever answered."""
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def credentials(settings: Settings) -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.service_token:
        headers["X-Service-Token"] = settings.service_token
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    return headers


async def forward(request: Request, client: httpx.AsyncClient, settings: Settings) -> Response:
    path = request.url.path
    if not is_allowed(request.method, path):
        log.info("web.forward_refused", method=request.method, path=path)
        return error("not_found", NOT_FOUND, status_code=404)

    headers = credentials(settings)
    if content_type := request.headers.get("content-type"):
        headers["Content-Type"] = content_type
    try:
        answer = await client.request(
            request.method,
            f"{settings.api_url}{path}",
            content=await request.body(),
            headers=headers,
            timeout=FORWARD_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as failure:
        log.warning("web.api_unreachable", path=path, error=type(failure).__name__)
        return error("api_unreachable", UNREACHABLE, status_code=502)

    log.info("web.forwarded", method=request.method, path=path, status=answer.status_code)
    passed: dict[str, Any] = {name: answer.headers[name] for name in PASSED_BACK_HEADERS if name in answer.headers}
    return Response(content=answer.content, status_code=answer.status_code, headers=passed)


async def api_is_up(client: httpx.AsyncClient, settings: Settings) -> bool:
    """Asks the API's liveness probe, waiting as long as a sleeping free-tier service takes to wake."""
    try:
        answer = await client.get(f"{settings.api_url}/health", timeout=WAKE_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return False
    return answer.status_code == 200
