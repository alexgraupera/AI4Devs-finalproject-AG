from decimal import Decimal

from app.domain.schemas.listing_review import Listing
from app.generation.agentic.ports import RegulationFragment
from app.generation.agentic.tools import CheckListingFields, SearchRegulations

A_TEXT = "Piso exterior de dos habitaciones en Chamberí, con cocina equipada y ascensor."


def a_listing(**fields: object) -> Listing:
    values: dict[str, object] = {
        "text": A_TEXT,
        "price_eur_month": Decimal(1_200),
        "usable_surface_m2": Decimal(65),
        "rooms": 2,
        "municipality": "Madrid",
        "energy_rating": "E",
    }
    values.update(fields)
    return Listing.model_validate(values)


def a_fragment(chunk_id: int = 36) -> RegulationFragment:
    return RegulationFragment(
        chunk_id=chunk_id,
        text="Artículo 36. Fianza. Una mensualidad de renta en el arrendamiento de viviendas.",
        score=0.7,
        law_id="BOE-A-1994-26003",
        law_title="Ley 29/1994, de Arrendamientos Urbanos",
        article_title="Artículo 36",
        citation_url="https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36",
        jurisdiction="state",
    )


class FakeSearch:
    def __init__(self, fragments: list[RegulationFragment] | None = None) -> None:
        self.fragments = [a_fragment()] if fragments is None else fragments
        self.calls: list[tuple[str, list[str] | None]] = []

    async def search_regulations(
        self, query: str, *, jurisdictions: list[str] | None = None
    ) -> list[RegulationFragment]:
        self.calls.append((query, jurisdictions))
        return self.fragments


# ── check_listing_fields ─────────────────────────────────────────────────────────────────────


async def test_reports_every_missing_mandatory_field() -> None:
    result = await CheckListingFields(a_listing(price_eur_month=None, energy_rating=None, municipality="")).run({})

    assert result.ok
    assert result.data["missing"] == ["el precio mensual", "el municipio", "la calificación energética"]


async def test_a_complete_listing_has_nothing_missing_and_no_contradiction() -> None:
    result = await CheckListingFields(a_listing()).run({})

    assert result.data == {"missing": [], "contradictions": []}


async def test_reports_a_rent_in_the_text_that_contradicts_the_price_field() -> None:
    listing = a_listing(text=f"{A_TEXT} Alquiler de 1.350 €/mes con comunidad incluida.")

    result = await CheckListingFields(listing).run({})

    assert result.data["contradictions"] == [
        "El texto indica un alquiler de 1350 € al mes y el campo precio dice 1200 €."
    ]


async def test_a_deposit_amount_is_not_read_as_the_rent() -> None:
    listing = a_listing(text=f"{A_TEXT} Fianza de 2.400 € y 1.200 € al mes.")

    assert (await CheckListingFields(listing).run({})).data["contradictions"] == []


async def test_reports_a_surface_in_the_text_that_contradicts_the_field() -> None:
    listing = a_listing(text=f"{A_TEXT} Tiene 80 m² útiles.")

    result = await CheckListingFields(listing).run({})

    assert result.data["contradictions"] == ["El texto indica 80 m² y el campo superficie útil dice 65 m²."]


# ── search_regulations ───────────────────────────────────────────────────────────────────────


async def test_numbers_the_fragments_and_carries_them_for_the_conductor() -> None:
    result = await SearchRegulations(FakeSearch()).run({"query": "fianza"})

    assert result.ok
    assert result.content.startswith("[36] Ley 29/1994, de Arrendamientos Urbanos · Artículo 36 (normativa estatal)")
    assert result.data["fragments"] == [a_fragment()]


async def test_an_empty_search_says_so_instead_of_failing() -> None:
    result = await SearchRegulations(FakeSearch(fragments=[])).run({"query": "seguro de hogar"})

    assert result.ok
    assert "No hay fragmentos" in result.content
    assert result.data["fragments"] == []


async def test_passes_the_jurisdiction_filter_through() -> None:
    search = FakeSearch()

    await SearchRegulations(search).run({"query": "oferta", "jurisdictions": ["catalonia"]})

    assert search.calls == [("oferta", ["catalonia"])]


async def test_keeps_at_most_the_configured_number_of_fragments() -> None:
    search = FakeSearch(fragments=[a_fragment(i) for i in range(1, 9)])

    result = await SearchRegulations(search, max_fragments=3).run({"query": "fianza"})

    assert [f.chunk_id for f in result.data["fragments"]] == [1, 2, 3]


async def test_arguments_that_do_not_match_the_spec_come_back_as_a_readable_error() -> None:
    tool = SearchRegulations(FakeSearch())

    missing = await tool.run({})
    unknown_region = await tool.run({"query": "fianza", "jurisdictions": ["andalucia"]})

    assert not missing.ok and "query" in missing.content
    assert not unknown_region.ok and "jurisdictions" in unknown_region.content
