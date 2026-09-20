import pytest

from app.ingestion.normalize import normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Artículo\xa031", "Artículo 31"),
        ("  Artículo 36.  Fianza.  ", "Artículo 36. Fianza."),
        ("A la celebración\n        del contrato", "A la celebración del contrato"),
        ("", ""),
    ],
)
def test_collapses_every_kind_of_whitespace(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_leaves_the_words_untouched() -> None:
    assert normalize("fianza en metálico en cantidad equivalente") == "fianza en metálico en cantidad equivalente"
