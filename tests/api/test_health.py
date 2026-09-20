from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_engine
from app.main import create_app


class FakeConnection:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    async def __aenter__(self) -> "FakeConnection":
        if self.error is not None:
            raise self.error
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: Any) -> None:
        return None


class FakeEngine:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def connect(self) -> FakeConnection:
        return FakeConnection(self.error)


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    yield application
    application.dependency_overrides.clear()


def client_with_engine(app: FastAPI, engine: object) -> TestClient:
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def test_reports_the_service_as_ok(app: FastAPI) -> None:
    response = client_with_engine(app, None).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_reports_the_database_as_disabled_when_it_is_not_configured(app: FastAPI) -> None:
    response = client_with_engine(app, None).get("/health")

    assert response.json()["database"] == "disabled"


def test_reports_the_database_as_unavailable_when_it_cannot_be_reached(app: FastAPI) -> None:
    response = client_with_engine(app, FakeEngine(error=OSError("connection refused"))).get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "unavailable"


def test_reports_the_database_as_ok_when_it_answers(app: FastAPI) -> None:
    response = client_with_engine(app, FakeEngine()).get("/health")

    assert response.json()["database"] == "ok"
