"""FastAPI application factory.

Composition root, above the layers: it wires the routers of `app/api/` and
nothing else. Business logic lives in `app/domain/`, the AI architectures in
`app/generation/` and the plumbing in `app/foundation/`.
"""

from fastapi import FastAPI

from app.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Rental Assistant API", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
