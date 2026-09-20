import pytest

from app.ingestion.boe.consolidated import LawMetadata, ParsedArticle
from app.ingestion.boe.resolutions import StressedAreaDeclaration
from app.ingestion.sources import CORPUS, DocType, Jurisdiction, Source, source_by_id
from app.ingestion.validation import (
    EMPTY_TEXT,
    MISSING_FECHA_VIGENCIA,
    MISSING_TITLE,
    RepealedSource,
    ensure_in_force,
    percentile,
    validate_articles,
    validate_declarations,
)

A_SOURCE = Source(
    source_id="BOE-A-1994-26003",
    title="Ley 29/1994",
    jurisdiction=Jurisdiction.STATE,
    doc_type=DocType.CONSOLIDATED_LAW,
)


def an_article(
    block_id: str = "a1", text: str = "Contenido", title: str = "Artículo 1", vigencia: str = "20190306"
) -> ParsedArticle:
    return ParsedArticle(
        block_id=block_id,
        article_title=title,
        text=text,
        fecha_vigencia=vigencia,
        id_norma="BOE-A-2019-3108",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a1",
    )


def a_law(*, repealed: bool = False, exhausted: bool = False) -> LawMetadata:
    return LawMetadata(
        source_id="BOE-A-1994-26003",
        title="Ley 29/1994",
        boe_updated_at="20260430T073359Z",
        url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003",
        repealed=repealed,
        exhausted=exhausted,
    )


@pytest.mark.parametrize(
    ("article", "reason"),
    [
        (an_article(text="   "), EMPTY_TEXT),
        (an_article(title=""), MISSING_TITLE),
        (an_article(vigencia=""), MISSING_FECHA_VIGENCIA),
    ],
)
def test_drops_an_unusable_article_and_says_why(article: ParsedArticle, reason: str) -> None:
    kept, report = validate_articles(A_SOURCE, [article])

    assert kept == []
    assert report.rejected == [type(report.rejected[0])(block_id=article.block_id, reason=reason)]


def test_a_bad_article_does_not_take_the_rest_of_the_law_with_it() -> None:
    kept, report = validate_articles(A_SOURCE, [an_article("a1"), an_article("a2", text=""), an_article("a3")])

    assert [a.block_id for a in kept] == ["a1", "a3"]
    assert report.parsed == 3
    assert report.kept == 2


def test_measures_the_sizes_of_what_survived() -> None:
    articles = [an_article("a1", text="x" * 100), an_article("a2", text="x" * 300), an_article("a3", text="x" * 2000)]

    _, report = validate_articles(A_SOURCE, articles)

    assert report.characters == 2400
    assert report.p50_chars == 300
    assert report.max_chars == 2000
    assert report.longest_block_id == "a3"


def test_an_empty_source_reports_zeros_instead_of_failing() -> None:
    _, report = validate_articles(A_SOURCE, [])

    assert (report.parsed, report.kept, report.characters, report.max_chars) == (0, 0, 0, 0)
    assert report.longest_block_id == ""


@pytest.mark.parametrize("sizes", [[10], [10, 20], [10, 20, 30, 40]])
def test_the_percentile_never_falls_outside_the_measured_sizes(sizes: list[int]) -> None:
    assert percentile(sizes, 95) in sizes
    assert percentile(sizes, 50) in sizes


def test_a_law_in_force_passes_the_gate() -> None:
    ensure_in_force(a_law())


@pytest.mark.parametrize("law", [a_law(repealed=True), a_law(exhausted=True)])
def test_a_law_no_longer_in_force_stops_the_ingestion_instead_of_being_counted(law: LawMetadata) -> None:
    # A repealed law is not a data quality statistic: it is the assistant citing dead rules.
    with pytest.raises(RepealedSource):
        ensure_in_force(law)


def test_an_empty_declaration_is_rejected() -> None:
    declarations = [
        StressedAreaDeclaration(
            source_id="BOE-A-2025-8636", block_id="d1", text="Lasarte-Oria", published_on="20250430", citation_url="u"
        ),
        StressedAreaDeclaration(
            source_id="BOE-A-2025-8636", block_id="d2", text="  ", published_on="20250430", citation_url="u"
        ),
    ]

    kept, report = validate_declarations(A_SOURCE, declarations)

    assert [d.block_id for d in kept] == ["d1"]
    assert [r.reason for r in report.rejected] == [EMPTY_TEXT]


def test_the_corpus_registry_has_no_duplicates_and_resolves_by_id() -> None:
    ids = [source.source_id for source in CORPUS]

    assert len(ids) == len(set(ids))
    assert source_by_id("BOE-A-2008-3657").jurisdiction == Jurisdiction.CATALONIA


def test_asking_for_a_source_outside_the_corpus_fails_loudly() -> None:
    with pytest.raises(KeyError):
        source_by_id("BOE-A-1900-1")
