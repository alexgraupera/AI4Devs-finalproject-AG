"""FastAPI application factory.

Composition root, above the layers: it wires the routers of `app/api/` and
nothing else. Business logic lives in `app/domain/`, the AI architectures in
`app/generation/` and the plumbing in `app/foundation/`.
"""

from fastapi import FastAPI

from app.api import feedback, health, listings, regulations
from app.api.errors import register_error_handlers
from app.api.request_id import RequestIdMiddleware
from app.api.security import ServiceTokenMiddleware
from app.config import Settings, get_settings
from app.foundation.observability.logging import configure_logging


class MissingProductionSettings(RuntimeError):
    """Production was asked to start without a secret it cannot run safely without."""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Fail fast, before serving a single request: an empty token or key does not fail later, it
    # silently opens the door. Names only in the message; a value never reaches a log.
    missing = settings.missing_for_production()
    if missing:
        raise MissingProductionSettings(f"production cannot start without: {', '.join(missing)}")

    configure_logging()
    app = FastAPI(title="Rental Assistant API", version="0.1.0")
    if settings.service_token:
        app.add_middleware(ServiceTokenMiddleware, token=settings.service_token)
    # Added last, so it runs first: a request the token rejects still gets an id to be found by.
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(listings.router)
    app.include_router(regulations.router)
    app.include_router(feedback.router)
    register_error_handlers(app)
    return app


app = create_app()
