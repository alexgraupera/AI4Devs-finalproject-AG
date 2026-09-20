from typing import TypeVar

from pydantic import BaseModel

from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    Listing,
    ListingReview,
    Severity,
    Verdict,
)

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """Records the prompts it receives and answers with a canned review."""

    def __init__(self, review: ListingReview) -> None:
        self.review = review
        self.system: str | None = None
        self.user: str | None = None

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        self.system = system
        self.user = user
        return self.review  # type: ignore[return-value]


def a_review() -> ListingReview:
    return ListingReview(
        findings=[
            Finding(
                category=FindingCategory.ENERGY_LABEL,
                severity=Severity.HIGH,
                message="Falta la calificación energética",
                suggestion="Añade la etiqueta de eficiencia energética",
                legal_basis="RD 390/2021 art. 15.2",
            )
        ],
        verdict=Verdict.REQUEST_CHANGES,
        summary="Falta información obligatoria",
    )


async def test_returns_the_review_produced_by_the_llm() -> None:
    review = a_review()
    service = ListingReviewService(llm=FakeLLM(review))

    assert await service.review(Listing(text="Piso en alquiler")) == review


async def test_sends_the_checklist_in_the_system_prompt_and_the_listing_in_the_user_prompt() -> None:
    llm = FakeLLM(a_review())
    service = ListingReviewService(llm=llm)

    await service.review(Listing(text="Piso exterior en Chamberí", municipality="Madrid"))

    assert llm.system is not None and "LAU art. 36.1" in llm.system
    assert llm.user is not None and "Piso exterior en Chamberí" in llm.user
    assert "Madrid" in llm.user
