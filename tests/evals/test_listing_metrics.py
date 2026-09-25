"""Scoring a review against an annotated listing: by law and article, legal findings only."""

import pytest

from evals.listings.metrics import ListingOutcome, citation_ref, legal_ref, summarise


@pytest.mark.parametrize(
    ("basis", "expected"),
    [
        ("LAU art. 36.1", ("LAU", "36")),
        ("Artículo 36 de la Ley 29/1994, de Arrendamientos Urbanos", ("LAU", "36")),
        ("Real Decreto 390/2021, artículo 15", ("RD 390/2021", "15")),
        ("RD 390/2021 art. 15", ("RD 390/2021", "15")),
        ("Ley 12/2023 art. 31", ("Ley 12/2023", "31")),
        ("Ley 18/2007, art. 61.2", ("Ley 18/2007", "61")),
        ("LAU", None),
        ("art. 36", None),
        (None, None),
        ("", None),
    ],
)
def test_a_legal_basis_is_its_law_and_article(basis: str | None, expected: tuple[str, str] | None) -> None:
    assert legal_ref(basis) == expected


def test_a_citation_names_its_law_by_boe_id() -> None:
    assert citation_ref("BOE-A-1994-26003", "Artículo 36. Fianza.") == ("LAU", "36")
    assert citation_ref("BOE-A-2026-16532", "Artículo 1") is None


def outcome(
    id: str,
    expected: set[tuple[str, str]],
    found: set[tuple[str, str]],
    *,
    tags: list[str] | None = None,
    verdict: str = "request_changes",
    expected_verdict: str = "request_changes",
    expected_error: str | None = None,
    error: str | None = None,
    escalated: bool = False,
) -> ListingOutcome:
    return ListingOutcome(
        id=id,
        tags=tags or [],
        expected=expected,
        expected_verdict=expected_verdict,
        expected_error=expected_error,
        found=found,
        verdict=verdict,
        error=error,
        escalated=escalated,
        cost_usd=0.01,
        latency_ms=1000,
    )


DEPOSIT = ("LAU", "36")
FEES = ("Ley 12/2023", "31")
ENERGY = ("RD 390/2021", "15")


def test_precision_and_recall_count_findings_across_listings() -> None:
    metrics = summarise(
        [
            outcome("a", {DEPOSIT, FEES}, {DEPOSIT}),
            outcome("b", {ENERGY}, {ENERGY, ("LAU", "20")}),
        ]
    )
    assert metrics.precision == pytest.approx(2 / 3)
    assert metrics.recall == pytest.approx(2 / 3)
    assert metrics.f1 == pytest.approx(2 / 3)


def test_a_clean_listing_with_any_legal_finding_is_a_false_positive() -> None:
    metrics = summarise(
        [
            outcome("clean-a", set(), set(), tags=["clean"], verdict="approve", expected_verdict="approve"),
            outcome("clean-b", set(), {DEPOSIT}, tags=["clean"], expected_verdict="approve"),
        ]
    )
    assert metrics.clean_false_positive_rate == 0.5
    assert metrics.verdict_accuracy == 0.5


def test_a_listing_that_must_be_refused_counts_only_as_adversarial() -> None:
    metrics = summarise(
        [
            outcome("ok", {DEPOSIT}, {DEPOSIT}),
            outcome("injection", set(), set(), expected_error="prompt_injection", error="prompt_injection"),
            outcome("pii", set(), {DEPOSIT}, expected_error="pii", verdict="request_changes"),
        ]
    )
    # The refused listings do not enter precision, recall or verdict accuracy.
    assert (metrics.precision, metrics.recall, metrics.verdict_accuracy) == (1.0, 1.0, 1.0)
    assert metrics.adversarial_handled == 0.5


def test_a_review_that_failed_is_a_failure_and_finds_nothing() -> None:
    metrics = summarise(
        [
            outcome("ok", {DEPOSIT}, {DEPOSIT}, escalated=True),
            outcome("down", {FEES}, set(), error="LLMUnavailable"),
        ]
    )
    assert metrics.failures == 1
    assert metrics.recall == 0.5
    assert metrics.escalation_rate == 1.0


def test_a_subset_without_clean_or_adversarial_listings_has_no_rate_for_them() -> None:
    metrics = summarise([outcome("ok", {DEPOSIT}, {DEPOSIT})])
    assert metrics.clean_false_positive_rate is None
    assert metrics.adversarial_handled is None
