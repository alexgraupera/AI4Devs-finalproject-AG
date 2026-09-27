"""The marketplace's web server: the built frontend, and the forwarding of its API calls.

In a real marketplace this is the business backend, the only party that holds the service token
and the API key (ADR 0020). Here it is also the static server of the frontend, so the browser talks
to one origin and needs no CORS.

- `GET /healthz`: liveness of this server. It never calls the API: a probe that depends on
  another service restarts this one whenever that one is asleep.
- `GET /bff/service`: is the API up? It waits for a sleeping API to wake, so the frontend can say
  so instead of failing.
- `/api/...`: forwarded to the API with the credentials, only for the calls in
  `web/forwarding.py`.
- Anything else: a file of `frontend/dist`, or `index.html` for the routes of the frontend.

Run it with `make web`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response

from app.config import Settings, get_settings
from app.foundation.observability.logging import configure_logging
from web.forwarding import NOT_FOUND, api_is_up, error, forward

DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"

NOT_BUILT = "The frontend is not built: run `npm --prefix frontend run build`, or use `make frontend` while developing."


def create_app(
    settings: Settings | None = None,
    *,
    dist_dir: Path = DIST_DIR,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """`transport` replaces the network in the tests, so no test ever calls a real API."""
    settings = settings or get_settings()
    dist = dist_dir.resolve()

    # One client for the life of the server: it keeps the connections to the API open between calls.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(transport=transport) as client:
            app.state.client = client
            yield

    configure_logging()
    app = FastAPI(title="Umbral web server", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/bff/service")
    async def service(request: Request) -> dict[str, str]:
        return {"api": "up" if await api_is_up(request.app.state.client, settings) else "down"}

    @app.api_route("/bff/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def unknown_bff(path: str) -> Response:
        return error("not_found", NOT_FOUND, status_code=404)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api(request: Request) -> Response:
        return await forward(request, request.app.state.client, settings)

    @app.get("/{path:path}")
    async def frontend(path: str) -> Response:
        index = dist / "index.html"
        if not index.is_file():
            return PlainTextResponse(NOT_BUILT, status_code=404)
        requested = (dist / path).resolve()
        # Never a file outside the build, whatever the path says.
        if requested.is_relative_to(dist) and requested.is_file():
            return FileResponse(requested)
        # A missing file is a 404; a route of the frontend (no extension) is the app itself.
        if Path(path).suffix:
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(index)

    return app


app = create_app()
