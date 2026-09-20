import httpx

from app.ingestion.boe.resolutions import fetch_declarations, parse_declarations
from tests.ingestion.fixtures import STRESSED_AREAS, xml


def declarations() -> list[str]:
    return [d.text for d in parse_declarations(xml("stressed_areas.xml"), STRESSED_AREAS)]


def test_extracts_one_declaration_per_declared_area() -> None:
    # The resolution of Q1 2025 declared four municipalities.
    areas = declarations()

    assert len(areas) == 4
    assert all("zona de mercado residencial tensionado" in area for area in areas)
    assert "Lasarte-Oria" in areas[0]


def test_does_not_count_the_second_listing_of_the_same_declarations() -> None:
    # Every declaration appears again below as "– Declaración: ..." with its links. Counting
    # both would put the same fact in the corpus twice.
    assert not any(area.startswith("Declaración:") for area in declarations())


def test_ignores_the_paragraphs_that_are_not_declarations() -> None:
    assert not any(area.startswith("En cumplimiento") for area in declarations())


def test_numbers_the_declarations_because_daily_items_have_no_block_ids() -> None:
    parsed = parse_declarations(xml("stressed_areas.xml"), STRESSED_AREAS)

    assert [d.block_id for d in parsed] == ["d1", "d2", "d3", "d4"]


def test_keeps_the_publication_date_and_a_citable_link() -> None:
    first = parse_declarations(xml("stressed_areas.xml"), STRESSED_AREAS)[0]

    assert first.published_on == "20250430"
    assert first.citation_url == "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-8636"


async def test_asks_the_daily_endpoint_for_the_resolution() -> None:
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=xml("stressed_areas.xml"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        parsed = await fetch_declarations(STRESSED_AREAS, client=client)

    assert seen["url"] == f"https://www.boe.es/diario_boe/xml.php?id={STRESSED_AREAS}"
    assert len(parsed) == 4
