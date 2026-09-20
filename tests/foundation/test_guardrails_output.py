from app.domain.schemas.listing_review import (
    Finding,
    FindingCategory,
    ListingReview,
    Severity,
    Verdict,
)
from app.foundation.guardrails.output import check_review


def a_finding(legal_basis: str | None, severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        category=FindingCategory.DEPOSIT_AND_GUARANTEES,
        severity=severity,
        message="La fianza supera una mensualidad",
        suggestion="Ajusta la fianza",
        legal_basis=legal_basis,
    )


def a_review(findings: list[Finding], verdict: Verdict = Verdict.REQUEST_CHANGES) -> ListingReview:
    return ListingReview(findings=findings, verdict=verdict, summary="Resumen")


def test_keeps_findings_citing_the_checklist() -> None:
    review = a_review([a_finding("LAU art. 36.1")])

    assert check_review(review) == review


def test_keeps_findings_without_a_legal_basis() -> None:
    review = a_review([a_finding(None, severity=Severity.LOW)], verdict=Verdict.APPROVE)

    assert check_review(review) == review


def test_drops_findings_citing_an_unknown_source() -> None:
    review = a_review([a_finding("LAU art. 99.9"), a_finding("LAU art. 36.1")])

    checked = check_review(review)

    assert [f.legal_basis for f in checked.findings] == ["LAU art. 36.1"]


def test_recomputes_the_verdict_when_the_only_high_finding_is_dropped() -> None:
    review = a_review([a_finding("Código Civil art. 1555")])

    checked = check_review(review)

    assert checked.findings == []
    assert checked.verdict == Verdict.APPROVE


def test_keeps_request_changes_when_a_high_finding_survives() -> None:
    review = a_review([a_finding("Inventada 1/2020"), a_finding("RD 390/2021 art. 15.2")])

    assert check_review(review).verdict == Verdict.REQUEST_CHANGES
