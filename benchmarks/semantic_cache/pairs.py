"""The pairs, and the one question they answer: can a threshold separate them?

A semantic cache is a similarity threshold. It is safe only if every pair that deserves the same
review scores above every pair that deserves a different one. The gap between those two groups is
the room a threshold has; a negative gap means no threshold exists that saves a call without
also serving a wrong review.
"""

import math
import pathlib
from dataclasses import dataclass
from enum import StrEnum

import yaml

PAIRS_FILE = pathlib.Path(__file__).parent / "pairs.yaml"


class PairKind(StrEnum):
    REWORDED = "reworded"
    CLAUSE_CHANGED = "clause-changed"
    DIFFERENT_FLAT = "different-flat"


@dataclass(frozen=True)
class ListingPair:
    id: str
    kind: PairKind
    a: str
    b: str

    @property
    def should_hit(self) -> bool:
        """Only a rewording deserves the stored review: anything else changes the answer."""
        return self.kind == PairKind.REWORDED


@dataclass(frozen=True)
class Separation:
    """The room a threshold has: the lowest pair that should hit against the highest that must not."""

    lowest_hit: float
    highest_miss: float

    @property
    def gap(self) -> float:
        return self.lowest_hit - self.highest_miss

    @property
    def separable(self) -> bool:
        return self.gap > 0


def load_pairs(path: pathlib.Path = PAIRS_FILE) -> list[ListingPair]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    pairs = [
        ListingPair(id=entry["id"], kind=PairKind(entry["kind"]), a=entry["a"], b=entry["b"])
        for entry in document["pairs"]
    ]
    ids = [pair.id for pair in pairs]
    duplicates = {id for id in ids if ids.count(id) > 1}
    if duplicates:
        raise ValueError(f"duplicate pair ids: {sorted(duplicates)}")
    return pairs


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norms = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norms if norms else 0.0


def separation(scored: list[tuple[ListingPair, float]]) -> Separation:
    hits = [score for pair, score in scored if pair.should_hit]
    misses = [score for pair, score in scored if not pair.should_hit]
    if not hits or not misses:
        raise ValueError("separation needs at least one pair that should hit and one that must not")
    return Separation(lowest_hit=min(hits), highest_miss=max(misses))
