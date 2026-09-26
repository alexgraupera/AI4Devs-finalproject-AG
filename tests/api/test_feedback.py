"""`POST /api/v1/feedback`: a vote is kept with the request it rates, and nothing it reviewed (#51)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_feedback_service, get_rate_limiter
from app.domain.feedback_service import FeedbackService
from app.foundation.guardrails.rate_limit import NoRateLimit
from app.main import create_app


class FakeStore:
    def __init__(self) -> None:
        self.saved: list[dict[str, object]] = []

    async def save(self, *, request_id: UUID, kind: str, rating: str, comment: str | None) -> tuple[int, datetime]:
        self.saved.append({"request_id": request_id, "kind": kind, "rating": rating, "comment": comment})
        return len(self.saved), datetime(2026, 9, 25, tzinfo=UTC)


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def app(store: FakeStore) -> Iterator[FastAPI]:
    application = create_app()
    application.dependency_overrides[get_feedback_service] = lambda: FeedbackService(store)
    yield application
    application.dependency_overrides.clear()


def vote(app: FastAPI, **fields: object) -> tuple[int, dict[str, Any]]:
    body = {"request_id": str(uuid4()), "kind": "listing_review", "rating": "down", **fields}
    response = TestClient(app, raise_server_exceptions=False).post("/api/v1/feedback", json=body)
    return response.status_code, response.json()


def test_a_vote_is_stored_with_the_request_it_rates(app: FastAPI, store: FakeStore) -> None:
    rated = str(uuid4())

    status, body = vote(app, request_id=rated, comment="La fianza de dos meses no la ha visto")

    assert status == 201
    assert body["request_id"] == rated
    assert store.saved == [
        {
            "request_id": UUID(rated),
            "kind": "listing_review",
            "rating": "down",
            "comment": "La fianza de dos meses no la ha visto",
        }
    ]


def test_an_unknown_kind_is_rejected(app: FastAPI, store: FakeStore) -> None:
    status, _ = vote(app, kind="weather_forecast")

    assert status == 422
    assert store.saved == []


def test_the_comment_is_capped(app: FastAPI, store: FakeStore) -> None:
    assert vote(app, comment="x" * 500)[0] == 201
    assert vote(app, comment="x" * 501)[0] == 422


def test_personal_data_in_a_comment_is_masked_not_refused(app: FastAPI, store: FakeStore) -> None:
    status, _ = vote(app, comment="Llamadme al 612 345 678 si hace falta")

    assert status == 201
    assert store.saved[0]["comment"] == "Llamadme al [dato personal] si hace falta"


def test_a_blank_comment_is_no_comment(app: FastAPI, store: FakeStore) -> None:
    vote(app, rating="up", comment="   ")

    assert store.saved[0]["comment"] is None


def test_the_endpoint_requires_the_api_key_when_one_is_configured(app: FastAPI, store: FakeStore) -> None:
    app.dependency_overrides[get_rate_limiter] = NoRateLimit
    app.dependency_overrides[get_settings] = lambda: Settings(api_key="a-key")
    body = {"request_id": str(uuid4()), "kind": "regulation_answer", "rating": "up"}

    without = TestClient(app).post("/api/v1/feedback", json=body)
    with_key = TestClient(app).post("/api/v1/feedback", json=body, headers={"X-API-Key": "a-key"})

    assert without.status_code == 401
    assert with_key.status_code == 201
    assert len(store.saved) == 1


def test_without_a_database_a_vote_says_it_could_not_be_kept(app: FastAPI) -> None:
    app.dependency_overrides[get_feedback_service] = lambda: FeedbackService(None)

    status, body = vote(app)

    assert status == 503
    assert body["error"]["code"] == "feedback_unavailable"
