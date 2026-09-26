"""A legal basis is its law and article, however it is written; an unknown law is None, never a guess."""

import pytest

from app.domain.legal_refs import citation_ref, legal_ref


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
        ("Código Civil art. 1555", None),
    ],
)
def test_a_legal_basis_is_its_law_and_article(basis: str | None, expected: tuple[str, str] | None) -> None:
    assert legal_ref(basis) == expected


def test_a_citation_names_its_law_by_boe_id() -> None:
    assert citation_ref("BOE-A-1994-26003", "Artículo 36. Fianza.") == ("LAU", "36")
    assert citation_ref("BOE-A-2026-16532", "Artículo 1") is None
