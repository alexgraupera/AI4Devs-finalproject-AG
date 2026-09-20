import pytest

from app.ingestion.boe.consolidated import ParsedArticle, parse_articles
from app.ingestion.boe.resolutions import StressedAreaDeclaration
from app.ingestion.chunking import (
    DECLARATION_TITLE,
    Chunk,
    chunk_article,
    chunk_declaration,
    content_hash,
    fixed_size_chunks,
)
from tests.ingestion.fixtures import LAU, TODAY, xml


def an_article(text: str, *, block_id: str = "a36", title: str = "Artículo 36") -> ParsedArticle:
    return ParsedArticle(
        block_id=block_id,
        article_title=title,
        text=text,
        fecha_vigencia="20190306",
        id_norma="BOE-A-2019-3108",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
    )


def paragraphs(count: int, size: int = 400) -> str:
    return "\n".join(f"{i}. {'x' * size}" for i in range(count))


def test_a_short_article_is_exactly_one_chunk() -> None:
    chunks = chunk_article(an_article("Artículo 36. Fianza. Una mensualidad."), max_chars=6_000)

    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].text == "Artículo 36. Fianza. Una mensualidad."
    assert chunks[0].char_count == len(chunks[0].text)


def test_a_chunk_carries_what_the_citation_needs() -> None:
    chunk = chunk_article(an_article("Fianza."), max_chars=6_000)[0]

    assert chunk.block_id == "a36"
    assert chunk.article_title == "Artículo 36"
    assert chunk.metadata == {
        "fecha_vigencia": "20190306",
        "id_norma": "BOE-A-2019-3108",
        "citation_url": "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
    }


def test_a_long_article_is_split_into_numbered_pieces() -> None:
    chunks = chunk_article(an_article(paragraphs(20)), max_chars=2_000)

    assert len(chunks) > 1
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.block_id == "a36" for chunk in chunks)


def test_a_split_never_cuts_a_paragraph_in_half() -> None:
    text = paragraphs(20)

    chunks = chunk_article(an_article(text), max_chars=2_000)

    rejoined = [line for chunk in chunks for line in chunk.text.split("\n")]
    assert [line for line in rejoined if not line.startswith("Artículo 36 (continuación)")] == text.split("\n")


def test_every_piece_of_a_split_article_says_which_article_it_is() -> None:
    # A chunk starting at "7. Durante los cinco primeros años..." is a rule with no subject.
    # The first piece carries the heading the BOE itself puts in the text; the rest get it added.
    body = f"Artículo 36. Fianza.\n{paragraphs(20)}"

    chunks = chunk_article(an_article(body), max_chars=2_000)

    assert len(chunks) > 1
    assert all("Artículo 36" in chunk.text for chunk in chunks)
    assert chunks[0].text.startswith("Artículo 36. Fianza.")
    assert all(chunk.text.startswith("Artículo 36 (continuación)") for chunk in chunks[1:])


def test_a_paragraph_longer_than_the_budget_goes_out_whole() -> None:
    # Nothing in the real corpus reaches this (the longest paragraph is 1,358 characters), but
    # cutting mid-sentence would be worse than one oversized chunk.
    chunks = chunk_article(an_article("x" * 5_000), max_chars=1_000)

    assert len(chunks) == 1
    assert chunks[0].char_count == 5_000


def test_the_same_text_always_hashes_the_same_and_a_reform_does_not() -> None:
    assert content_hash("Artículo 36. Fianza.") == content_hash("Artículo 36. Fianza.")
    assert content_hash("Artículo 36. Fianza.") != content_hash("Artículo 36. Fianza de dos mensualidades.")


def test_the_hash_travels_with_the_chunk() -> None:
    chunk = chunk_article(an_article("Fianza."), max_chars=6_000)[0]

    assert chunk.content_hash == content_hash("Fianza.")


def test_a_declaration_becomes_one_citable_chunk() -> None:
    declaration = StressedAreaDeclaration(
        source_id="BOE-A-2025-8636",
        block_id="d1",
        text="Resolución de 29 de abril de 2025, por la que se declara el municipio de Lasarte-Oria como zona...",
        published_on="20250430",
        citation_url="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-8636",
    )

    chunk = chunk_declaration(declaration)

    assert chunk.block_id == "d1"
    assert chunk.ordinal == 0
    assert chunk.article_title == DECLARATION_TITLE
    assert chunk.metadata["fecha_vigencia"] == "20250430"
    assert chunk.metadata["citation_url"].endswith("BOE-A-2025-8636")


def test_the_real_corpus_splits_almost_nothing_at_the_chosen_budget() -> None:
    articles = parse_articles(xml("lau_texto.xml"), LAU, today=TODAY)

    chunks = [chunk for article in articles for chunk in chunk_article(article, max_chars=6_000)]

    assert len(chunks) == len(articles)


def test_the_fixed_size_baseline_cuts_wherever_it_lands() -> None:
    pieces = fixed_size_chunks("abcdefghij", size=4, overlap=1)

    assert pieces == ["abcd", "defg", "ghij", "j"]


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (10, 10), (10, 20)])
def test_a_nonsensical_baseline_configuration_is_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="size must be positive"):
        fixed_size_chunks("abc", size=size, overlap=overlap)


def test_chunks_are_comparable_by_value() -> None:
    first, second = (chunk_article(an_article("Fianza."), max_chars=6_000)[0] for _ in range(2))

    assert isinstance(first, Chunk)
    assert first == second
