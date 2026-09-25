"""Every response carries the id of its request, and every log event of that request carries it too (#51)."""

from collections.abc import Iterator
from uuid import UUID

import pytest
import structlog
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_listing_review_service
from app.domain.schemas.listing_review import Listing, ListingReview, ReviewedListing, Verdict
from app.main import create_app
from tests.domain.test_listing_review_service import A_USAGE

A_LISTING = {
    "text": "Piso de dos habitaciones en Chamberí, con ascensor. Fianza de dos meses.",
    "municipality": "Madrid",
}


class RecordingService:
    """Reviews nothing; records what the logs of the request would carry while it runs."""

    def __init__(self) -> None:
        self.bound: dict[str, object] = {}

    async def review(self, listing: Listing) -> ReviewedListing:
        self.bound = structlog.contextvars.get_contextvars()
        review = ListingReview(findings=[], verdict=Verdict.APPROVE, summary="Sin incidencias.")
        return ReviewedListing(review=review, usage=A_USAGE)


@pytest.fixture
def service() -> RecordingService:
    return RecordingService()


@pytest.fixture
def client(service: RecordingService) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_listing_review_service] = lambda: service
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_every_response_carries_a_fresh_id(client: TestClient) -> None:
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert UUID(first) and UUID(second)
    assert first != second


def test_a_review_carries_the_id_of_its_request_in_the_body_and_the_header(client: TestClient) -> None:
    response = client.post("/api/v1/listings/review", json=A_LISTING)

    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_the_id_is_bound_to_the_log_events_of_that_request_and_only_that_one(
    client: TestClient, service: RecordingService
) -> None:
    response = client.post("/api/v1/listings/review", json=A_LISTING)

    assert service.bound["request_id"] == response.headers["X-Request-ID"]
    assert "request_id" not in structlog.contextvars.get_contextvars()


def test_an_error_carries_an_id_too(client: TestClient) -> None:
    response = client.post("/api/v1/listings/review", json={"municipality": "Madrid"})

    assert response.status_code == 422
    assert UUID(response.headers["X-Request-ID"])


def test_a_request_the_service_token_rejects_still_gets_an_id() -> None:
    app = create_app(Settings(service_token="a-token"))

    response = TestClient(app).post("/api/v1/listings/review", json=A_LISTING)

    assert response.status_code == 401
    assert UUID(response.headers["X-Request-ID"])


def test_the_id_is_generated_never_taken_from_the_caller(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "chosen-by-the-caller"})

    assert response.headers["X-Request-ID"] != "chosen-by-the-caller"
