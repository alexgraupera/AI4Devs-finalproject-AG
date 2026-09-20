"""FastAPI application factory.

Composition root, above the layers: it wires the routers of `app/api/` and
nothing else. Business logic lives in `app/domain/`, the AI architectures in
`app/generation/` and the plumbing in `app/foundation/`.
"""

from fastapi import FastAPI

from app.api import health, listings, regulations
from app.api.errors import register_error_handlers
from app.foundation.observability.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Rental Assistant API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(listings.router)
    app.include_router(regulations.router)
    register_error_handlers(app)
    return app


app = create_app()
