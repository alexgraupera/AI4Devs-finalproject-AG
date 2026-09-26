"""The annotated listings, loaded and checked."""

import pathlib
from dataclasses import dataclass, field

import yaml

from app.domain.legal_refs import LegalRef, legal_ref
from app.domain.schemas.listing_review import Listing

DATASET = pathlib.Path(__file__).parents[1] / "datasets" / "listings.yaml"


@dataclass(frozen=True)
class AnnotatedListing:
    id: str
    listing: Listing
    tags: list[str] = field(default_factory=list)
    expected_legal: set[LegalRef] = field(default_factory=set)
    expected_verdict: str | None = None
    expected_error: str | None = None


def load_listings(path: pathlib.Path = DATASET) -> list[AnnotatedListing]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    listings = []
    for entry in document["listings"]:
        expected = set()
        for basis in entry.get("expected_legal") or []:
            ref = legal_ref(basis)
            if ref is None:
                raise ValueError(f"{entry['id']}: '{basis}' does not name a known law and article")
            expected.add(ref)
        listings.append(
            AnnotatedListing(
                id=entry["id"],
                listing=Listing.model_validate(entry["listing"]),
                tags=list(entry.get("tags") or []),
                expected_legal=expected,
                expected_verdict=entry.get("expected_verdict"),
                expected_error=entry.get("expected_error"),
            )
        )
    ids = [listing.id for listing in listings]
    duplicates = {id for id in ids if ids.count(id) > 1}
    if duplicates:
        raise ValueError(f"duplicate listing ids: {sorted(duplicates)}")
    return listings
