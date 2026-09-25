"""Scoring a review against an annotated listing: legal findings only, by law and article."""

import pytest

from evals.listings.metrics import Failure, ListingOutcome, classify, summarise


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


# ── Failures, by the step that lost them ──────────────────────────────────────────────────


def test_an_article_the_agent_never_read_is_lost_by_the_search() -> None:
    lost = outcome("a", {DEPOSIT}, set())
    assert classify(lost, traced=True) == [Failure.NOT_READ]


def test_an_article_read_and_not_reported_is_lost_by_the_actor() -> None:
    lost = outcome("a", {DEPOSIT}, set())
    lost.read = {DEPOSIT}
    assert classify(lost, traced=True) == [Failure.READ_NOT_REPORTED]


def test_an_article_reported_and_rejected_is_lost_by_the_critic() -> None:
    lost = outcome("a", {DEPOSIT}, set())
    lost.read = {DEPOSIT}
    lost.rejected = [(DEPOSIT, "wrong_article")]
    assert classify(lost, traced=True) == [Failure.REJECTED_BY_CRITIC]


def test_without_a_trace_a_miss_is_only_a_miss() -> None:
    assert classify(outcome("a", {DEPOSIT}, set()), traced=False) == [Failure.MISSED]


def test_an_extra_article_is_invented_and_a_wrong_verdict_counts_on_its_own() -> None:
    wrong = outcome("clean", set(), {FEES}, tags=["clean"], expected_verdict="approve")
    assert classify(wrong, traced=True) == [Failure.INVENTED, Failure.WRONG_VERDICT]


def test_a_refusal_that_did_not_happen_and_a_run_that_failed_are_failures_of_their_own() -> None:
    obeyed = outcome("injection", set(), set(), expected_error="prompt_injection")
    down = outcome("a", {DEPOSIT}, set(), error="LLMUnavailable")
    assert classify(obeyed, traced=True) == [Failure.NOT_REFUSED]
    assert classify(down, traced=True) == [Failure.RUN_FAILED]
