from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_engine, get_redis, get_spend_guard
from app.foundation.guardrails.spend import BudgetExhausted, NoSpendLimit
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
        self.connections = 0

    def connect(self) -> FakeConnection:
        self.connections += 1
        return FakeConnection(self.error)


class FakeRedis:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def ping(self) -> bool:
        if self.error is not None:
            raise self.error
        return True


class ExhaustedBudget:
    async def check(self) -> None:
        raise BudgetExhausted(retry_after=3_600)

    async def record(self, cost_usd: object) -> None:
        return None


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = create_app()
    application.dependency_overrides[get_engine] = lambda: None
    application.dependency_overrides[get_redis] = lambda: None
    application.dependency_overrides[get_spend_guard] = NoSpendLimit
    yield application
    application.dependency_overrides.clear()


# ── Liveness ────────────────────────────────────────────────────────────────────────────────


def test_health_says_the_process_is_alive(app: FastAPI) -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_no_io_even_when_the_database_is_down(app: FastAPI) -> None:
    # A liveness probe that checks the database restarts a healthy service on every hiccup.
    engine = FakeEngine(error=OSError("connection refused"))
    app.dependency_overrides[get_engine] = lambda: engine

    assert TestClient(app).get("/health").status_code == 200
    assert engine.connections == 0


# ── Readiness ───────────────────────────────────────────────────────────────────────────────


def test_ready_without_a_database_configured(app: FastAPI) -> None:
    # The listing review does not need one, so a disabled store is a state, not a failure.
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "disabled", "cache": "disabled", "budget": "ok"}


def test_ready_when_every_dependency_answers(app: FastAPI) -> None:
    app.dependency_overrides[get_engine] = lambda: FakeEngine()
    app.dependency_overrides[get_redis] = lambda: FakeRedis()

    body = TestClient(app).get("/ready").json()

    assert body["database"] == "ok"
    assert body["cache"] == "ok"


def test_not_ready_when_the_database_cannot_be_reached(app: FastAPI) -> None:
    app.dependency_overrides[get_engine] = lambda: FakeEngine(error=OSError("connection refused"))

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.headers["Retry-After"] == "30"


def test_the_cache_being_down_is_reported_but_does_not_make_it_unready(app: FastAPI) -> None:
    # The cache, the rate limiter and the spend guard all fail open.
    app.dependency_overrides[get_redis] = lambda: FakeRedis(error=OSError("cache is down"))

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json()["cache"] == "unavailable"


def test_not_ready_until_midnight_when_the_budget_is_spent(app: FastAPI) -> None:
    app.dependency_overrides[get_spend_guard] = ExhaustedBudget

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["budget"] == "exhausted"
    assert response.headers["Retry-After"] == "3600"
