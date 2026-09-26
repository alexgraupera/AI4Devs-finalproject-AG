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
from app.foundation.guardrails.spend import BudgetExhausted
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


class FakeCache:
    """A cache that remembers what it was told, and says what it was asked."""

    def __init__(self, stored: ListingReview | None = None) -> None:
        self.stored = stored
        self.saved: dict[str, ListingReview] = {}
        self.keys_asked: list[str] = []

    async def get(self, key: str) -> ListingReview | None:
        self.keys_asked.append(key)
        return self.stored

    async def set(self, key: str, review: ListingReview) -> None:
        self.saved[key] = review


async def test_does_not_call_the_llm_on_a_cache_hit() -> None:
    llm = FakeLLM(a_candidate())
    cached_review = a_candidate().to_review()
    service = ListingReviewService(llm=llm, cache=FakeCache(stored=cached_review))

    reviewed = await service.review(A_LISTING)

    assert reviewed.cached is True
    assert reviewed.review == cached_review
    assert llm.system is None


async def test_a_cache_hit_reports_no_tokens_and_no_cost() -> None:
    service = ListingReviewService(llm=FakeLLM(a_candidate()), cache=FakeCache(stored=a_candidate().to_review()))

    usage = (await service.review(A_LISTING)).usage

    assert usage.provider == "cache"
    assert (usage.input_tokens, usage.output_tokens, usage.attempts) == (0, 0, 0)
    assert usage.estimated_cost_usd == Decimal(0)


async def test_stores_the_review_on_a_cache_miss() -> None:
    cache = FakeCache()
    service = ListingReviewService(llm=FakeLLM(a_candidate()), cache=cache)

    reviewed = await service.review(A_LISTING)

    assert reviewed.cached is False
    assert list(cache.saved.values()) == [reviewed.review]


async def test_the_cache_key_changes_with_the_prompt_version() -> None:
    first = FakeCache()
    second = FakeCache()

    await ListingReviewService(llm=FakeLLM(a_candidate()), cache=first, prompt_version="v1").review(A_LISTING)
    await ListingReviewService(llm=FakeLLM(a_candidate()), cache=second, prompt_version="v2").review(A_LISTING)

    assert first.keys_asked != second.keys_asked


async def test_does_not_store_a_text_that_is_not_a_listing() -> None:
    cache = FakeCache()
    service = ListingReviewService(llm=FakeLLM(a_candidate(is_rental_listing=False)), cache=cache)

    with pytest.raises(NotAListing):
        await service.review(A_LISTING)

    assert cache.saved == {}


# ── The daily spend cap ─────────────────────────────────────────────────────────────────────


class RecordingSpend:
    def __init__(self, exhausted: bool = False) -> None:
        self.exhausted = exhausted
        self.recorded: list[Decimal | None] = []

    async def check(self) -> None:
        if self.exhausted:
            raise BudgetExhausted(retry_after=60)

    async def record(self, cost_usd: Decimal | None) -> None:
        self.recorded.append(cost_usd)


async def test_records_what_the_review_cost() -> None:
    spend = RecordingSpend()

    await ListingReviewService(llm=FakeLLM(a_candidate()), spend=spend).review(A_LISTING)

    assert spend.recorded == [A_USAGE.estimated_cost_usd]


async def test_an_exhausted_budget_stops_the_review_before_the_model_is_called() -> None:
    llm = FakeLLM(a_candidate())

    with pytest.raises(BudgetExhausted):
        await ListingReviewService(llm=llm, spend=RecordingSpend(exhausted=True)).review(A_LISTING)

    assert llm.system is None


async def test_a_text_that_is_not_a_listing_still_counts_against_the_budget() -> None:
    # The model was asked and paid for, whatever it answered.
    spend = RecordingSpend()

    with pytest.raises(NotAListing):
        await ListingReviewService(llm=FakeLLM(a_candidate(is_rental_listing=False)), spend=spend).review(A_LISTING)

    assert spend.recorded == [A_USAGE.estimated_cost_usd]
