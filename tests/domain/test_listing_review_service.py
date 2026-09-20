from decimal import Decimal
from typing import TypeVar

import pytest
from pydantic import BaseModel

from app.domain.errors import LLMUnavailable, NotAListing, ReviewGenerationError
from app.domain.listing_review_service import ListingReviewService
from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    Listing,
    ListingReview,
    ReviewCandidate,
    Severity,
    Verdict,
)
from app.foundation.guardrails.input import InputGuardrailViolation
from app.foundation.llm.usage import LLMUsage, StructuredCompletion

T = TypeVar("T", bound=BaseModel)

A_USAGE = LLMUsage(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=1_000,
    output_tokens=500,
    latency_ms=1_234,
    estimated_cost_usd=Decimal("0.0035"),
)

A_LISTING = Listing(
    text=(
        "Piso exterior de dos habitaciones en Chamberí, con cocina equipada, calefacción "
        "central y ascensor. Se pide fianza de dos meses."
    ),
    municipality="Madrid",
)


def a_candidate(
    *, is_rental_listing: bool = True, legal_basis: str | None = "RD 390/2021 art. 15.2"
) -> ReviewCandidate:
    return ReviewCandidate(
        is_rental_listing=is_rental_listing,
        findings=[
            Finding(
                category=FindingCategory.ENERGY_LABEL,
                severity=Severity.HIGH,
                message="Falta la calificación energética",
                suggestion="Añade la etiqueta de eficiencia energética",
                legal_basis=legal_basis,
            )
        ],
        verdict=Verdict.REQUEST_CHANGES,
        summary="Falta información obligatoria",
    )


class FakeLLM:
    """Records the prompts it receives and answers with a canned candidate, or raises."""

    def __init__(self, candidate: ReviewCandidate | None = None, error: Exception | None = None) -> None:
        self.candidate = candidate
        self.error = error
        self.system: str | None = None
        self.user: str | None = None

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        self.system = system
        self.user = user
        if self.error is not None:
            raise self.error
        return StructuredCompletion(output=self.candidate, usage=A_USAGE)  # type: ignore[arg-type]


async def test_returns_the_review_produced_by_the_llm() -> None:
    service = ListingReviewService(llm=FakeLLM(a_candidate()))

    reviewed = await service.review(A_LISTING)

    assert reviewed.review == a_candidate().to_review()
    assert reviewed.usage == A_USAGE


async def test_sends_the_checklist_in_the_system_prompt_and_the_listing_in_the_user_prompt() -> None:
    llm = FakeLLM(a_candidate())
    service = ListingReviewService(llm=llm)

    await service.review(A_LISTING)

    assert llm.system is not None and "LAU art. 36.1" in llm.system
    assert llm.user is not None and "Piso exterior de dos habitaciones" in llm.user
    assert "Madrid" in llm.user


async def test_wraps_the_listing_in_delimiters() -> None:
    llm = FakeLLM(a_candidate())
    service = ListingReviewService(llm=llm)

    await service.review(A_LISTING)

    assert llm.user is not None
    assert "<anuncio>" in llm.user and "</anuncio>" in llm.user


async def test_rejects_the_listing_before_calling_the_llm() -> None:
    llm = FakeLLM(a_candidate())
    service = ListingReviewService(llm=llm)

    with pytest.raises(InputGuardrailViolation):
        await service.review(Listing(text="Piso"))

    assert llm.system is None


async def test_rejects_text_that_is_not_a_rental_listing() -> None:
    service = ListingReviewService(llm=FakeLLM(a_candidate(is_rental_listing=False)))

    with pytest.raises(NotAListing):
        await service.review(A_LISTING)


async def test_drops_findings_citing_a_source_outside_the_checklist() -> None:
    service = ListingReviewService(llm=FakeLLM(a_candidate(legal_basis="LAU art. 99.9")))

    reviewed = await service.review(A_LISTING)

    assert reviewed.review.findings == []
    assert reviewed.review.verdict == Verdict.APPROVE


@pytest.mark.parametrize("error", [ReviewGenerationError("invalid"), LLMUnavailable("timeout")])
async def test_propagates_the_llm_errors(error: Exception) -> None:
    service = ListingReviewService(llm=FakeLLM(error=error))

    with pytest.raises(type(error)):
        await service.review(A_LISTING)


async def test_returns_an_untouched_review_when_everything_is_in_order() -> None:
    service = ListingReviewService(llm=FakeLLM(a_candidate()))

    assert isinstance((await service.review(A_LISTING)).review, ListingReview)
