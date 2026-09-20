from collections.abc import Iterator
from typing import TypeVar

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.dependencies import get_listing_review_service
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    ListingReview,
    Severity,
    Verdict,
)
from app.main import create_app

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        return ListingReview(  # type: ignore[return-value]
            findings=[
                Finding(
                    category=FindingCategory.DEPOSIT_AND_GUARANTEES,
                    severity=Severity.HIGH,
                    message="La fianza supera una mensualidad",
                    suggestion="Ajusta la fianza a una mensualidad",
                    legal_basis="LAU art. 36.1",
                )
            ],
            verdict=Verdict.REQUEST_CHANGES,
            summary="Hay que corregir la fianza",
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_listing_review_service] = lambda: ListingReviewService(llm=FakeLLM())
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_returns_the_structured_review(client: TestClient) -> None:
    response = client.post(
        "/api/v1/listings/review",
        json={"text": "Piso en alquiler, fianza de dos meses", "municipality": "Madrid"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "request_changes"
    assert body["summary"] == "Hay que corregir la fianza"
    assert body["findings"] == [
        {
            "category": "deposit_and_guarantees",
            "severity": "high",
            "message": "La fianza supera una mensualidad",
            "suggestion": "Ajusta la fianza a una mensualidad",
            "legal_basis": "LAU art. 36.1",
        }
    ]


def test_rejects_a_request_without_text(client: TestClient) -> None:
    response = client.post("/api/v1/listings/review", json={"municipality": "Madrid"})

    assert response.status_code == 422
