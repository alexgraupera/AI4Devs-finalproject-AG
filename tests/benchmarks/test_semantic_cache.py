"""The separation logic and the pairs file. Running it for real is `make benchmark-semantic-cache`."""

import pytest

from benchmarks.semantic_cache.pairs import ListingPair, PairKind, cosine, load_pairs, separation


def a_pair(kind: PairKind, id: str = "pair") -> ListingPair:
    return ListingPair(id=id, kind=kind, a="a", b="b")


def test_only_a_rewording_deserves_the_stored_review() -> None:
    assert a_pair(PairKind.REWORDED).should_hit
    assert not a_pair(PairKind.CLAUSE_CHANGED).should_hit
    assert not a_pair(PairKind.DIFFERENT_FLAT).should_hit


def test_identical_vectors_are_fully_similar_and_orthogonal_ones_not_at_all() -> None:
    assert cosine([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_a_zero_vector_is_not_similar_to_anything() -> None:
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_separable_when_every_rewording_scores_above_every_changed_clause() -> None:
    result = separation([(a_pair(PairKind.REWORDED), 0.95), (a_pair(PairKind.CLAUSE_CHANGED), 0.90)])

    assert result.separable
    assert result.gap == pytest.approx(0.05)


def test_not_separable_when_a_changed_clause_scores_above_a_rewording() -> None:
    result = separation(
        [
            (a_pair(PairKind.REWORDED), 0.93),
            (a_pair(PairKind.REWORDED), 0.97),
            (a_pair(PairKind.CLAUSE_CHANGED), 0.98),
            (a_pair(PairKind.DIFFERENT_FLAT), 0.60),
        ]
    )

    assert not result.separable
    assert result.lowest_hit == pytest.approx(0.93)
    assert result.highest_miss == pytest.approx(0.98)


def test_separation_needs_both_kinds_of_pair() -> None:
    with pytest.raises(ValueError):
        separation([(a_pair(PairKind.REWORDED), 0.9)])


def test_the_pairs_file_covers_every_kind_with_unique_ids() -> None:
    pairs = load_pairs()

    assert {pair.kind for pair in pairs} == set(PairKind)
    assert len({pair.id for pair in pairs}) == len(pairs)
    assert all(pair.a.strip() and pair.b.strip() and pair.a != pair.b for pair in pairs)
