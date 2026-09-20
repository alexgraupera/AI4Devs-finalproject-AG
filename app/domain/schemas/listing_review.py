"""The contract of the review: what goes in, what comes out.

`ListingReview` is also the schema the model must fill, so its field order and
descriptions are part of the prompt. Keep the summary last: the model writes it
after having committed to the findings, not before.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.foundation.llm.usage import LLMUsage


class Listing(BaseModel):
    """A rental listing as the landlord or agency wrote it, plus optional structured fields."""

    text: str
    price_eur_month: Decimal | None = None
    usable_surface_m2: Decimal | None = None
    rooms: int | None = None
    municipality: str | None = None
    energy_rating: str | None = None


class FindingCategory(StrEnum):
    ENERGY_LABEL = "energy_label"
    PRICE_AND_EXPENSES = "price_and_expenses"
    DEPOSIT_AND_GUARANTEES = "deposit_and_guarantees"
    AGENCY_FEES = "agency_fees"
    SURFACE = "surface"
    PROPERTY_DETAILS = "property_details"
    DESCRIPTION_QUALITY = "description_quality"
    OTHER = "other"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Verdict(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"


class Finding(BaseModel):
    category: FindingCategory
    severity: Severity = Field(description="high: it breaks the law or blocks publication; low: style")
    message: str = Field(description="What is wrong, in Spanish, addressed to the person publishing")
    suggestion: str = Field(description="What to do about it, in Spanish and concrete")
    legal_basis: str | None = Field(
        default=None,
        description="Article backing the finding, e.g. 'LAU art. 36.1'. Null when the finding is not legal",
    )


class ListingReview(BaseModel):
    findings: list[Finding]
    verdict: Verdict = Field(description="request_changes when there is any finding of high severity")
    summary: str = Field(description="One or two sentences in Spanish summarising the review")


class ReviewCandidate(BaseModel):
    """What the model is asked to fill, before the guardrails have their say.

    `is_rental_listing` is first on purpose: the model decides what it is looking at before it
    starts producing findings about it.
    """

    is_rental_listing: bool = Field(description="False when the text is not a rental listing at all")
    findings: list[Finding]
    verdict: Verdict = Field(description="request_changes when there is any finding of high severity")
    summary: str = Field(description="One or two sentences in Spanish summarising the review")

    def to_review(self) -> ListingReview:
        return ListingReview(findings=self.findings, verdict=self.verdict, summary=self.summary)


@dataclass(frozen=True)
class ReviewedListing:
    """What a review costs is part of what a review is: both travel together."""

    review: ListingReview
    usage: LLMUsage
    cached: bool = False
