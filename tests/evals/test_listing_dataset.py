"""The annotated listings are well formed: a broken annotation would score the model, not the data."""

import re

import pytest

from app.domain.schemas.listing_review import Verdict
from evals.listings.dataset import AnnotatedListing, load_listings
from evals.listings.metrics import legal_ref

LISTINGS = load_listings()


def test_the_dataset_covers_every_kind_of_listing() -> None:
    tags = {tag for listing in LISTINGS for tag in listing.tags}
    assert {"clean", "trap", "violation", "regional", "adversarial", "injection", "pii"} <= tags
    assert len(LISTINGS) >= 15


@pytest.mark.parametrize("case", LISTINGS, ids=lambda case: case.id)
def test_every_listing_is_annotated_with_an_outcome(case: AnnotatedListing) -> None:
    if case.expected_error:
        assert case.expected_verdict is None
    else:
        assert case.expected_verdict in set(Verdict)
    if "clean" in case.tags:
        assert not case.expected_legal and case.expected_verdict == Verdict.APPROVE
    if "violation" in case.tags:
        assert case.expected_legal and case.expected_verdict == Verdict.REQUEST_CHANGES


def test_only_the_personal_data_listing_carries_personal_data() -> None:
    phone = re.compile(r"(?<!\d)(?:\+34[\s.-]?)?[6-9](?:[\s.-]?\d){8}(?!\d)")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    iban = re.compile(r"\bES\d{2}(?:\s?\d{4}){5}\b")
    carriers = {case.id for case in LISTINGS if any(p.search(case.listing.text) for p in (phone, email, iban))}
    assert carriers == {case.id for case in LISTINGS if case.expected_error == "pii"}


def test_an_unknown_legal_basis_is_rejected() -> None:
    assert legal_ref("Código Civil art. 1555") is None
