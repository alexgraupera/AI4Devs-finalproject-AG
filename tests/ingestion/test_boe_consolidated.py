import httpx
import pytest

from app.ingestion.boe.consolidated import (
    ParsedArticle,
    fetch_articles,
    fetch_metadata,
    parse_articles,
    parse_metadata,
)
from tests.ingestion.fixtures import CATALONIA, LAU, TODAY, metadata, xml


def lau_articles() -> list[ParsedArticle]:
    return parse_articles(xml("lau_texto.xml"), LAU, today=TODAY)


def article(articles: list[ParsedArticle], block_id: str) -> ParsedArticle:
    return next(a for a in articles if a.block_id == block_id)


def a_block(versions: str, block_id: str = "a1", tipo: str = "precepto", titulo: str = "Artículo 1") -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <response><data><texto>
      <bloque id="{block_id}" tipo="{tipo}" titulo="{titulo}">{versions}</bloque>
    </texto></data></response>""".encode()


def test_keeps_only_the_articles_and_leaves_the_scaffolding_out() -> None:
    # The fixture also carries a heading, a signature and (in the Catalan law) an initial note.
    assert [a.block_id for a in lau_articles()] == ["a20", "a36"]


def test_reads_the_article_title_from_the_block() -> None:
    assert article(lau_articles(), "a36").article_title == "Artículo 36"


def test_picks_the_version_in_force_and_not_simply_the_last_one() -> None:
    # Article 36 carries seven versions, from 1995 to 2019.
    deposit = article(lau_articles(), "a36")

    assert deposit.fecha_vigencia == "20190306"
    assert deposit.id_norma == "BOE-A-2019-3108"
    assert "una mensualidad de renta en el arrendamiento de viviendas" in deposit.text


def test_ignores_a_version_that_is_not_in_force_yet() -> None:
    future = a_block(
        '<version id_norma="BOE-A-2020-1" fecha_vigencia="20200101"><p>Redacción vigente</p></version>'
        '<version id_norma="BOE-A-2030-1" fecha_vigencia="20300101"><p>Redacción futura</p></version>'
    )

    parsed = parse_articles(future, LAU, today=TODAY)

    assert parsed[0].text == "Redacción vigente"


def test_skips_a_block_whose_every_version_is_still_in_the_future() -> None:
    not_yet = a_block('<version id_norma="BOE-A-2030-1" fecha_vigencia="20300101"><p>Redacción futura</p></version>')

    assert parse_articles(not_yet, LAU, today=TODAY) == []


def test_normalises_the_non_breaking_spaces_the_boe_mixes_in() -> None:
    spaced = a_block(
        '<version id_norma="BOE-A-2020-1" fecha_vigencia="20200101"><p>Artículo\xa01.\n   Objeto.</p></version>',
        titulo="Artículo\xa01",
    )

    parsed = parse_articles(spaced, LAU, today=TODAY)

    assert parsed[0].article_title == "Artículo 1"
    assert parsed[0].text == "Artículo 1. Objeto."


def test_builds_the_citation_url_from_the_law_and_the_block() -> None:
    assert article(lau_articles(), "a36").citation_url == "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36"


def test_parses_a_regional_law_with_the_very_same_parser() -> None:
    articles = parse_articles(xml("catalonia_texto.xml"), CATALONIA, today=TODAY)
    offer = article(articles, "a61")

    assert offer.article_title == "Artículo 61"
    assert "ofertas de arrendamiento" in offer.text
    assert offer.citation_url == "https://www.boe.es/buscar/act.php?id=BOE-A-2008-3657#a61"


def test_reads_the_metadata_that_decides_a_reingestion() -> None:
    law = parse_metadata(metadata("lau_metadatos.json"), LAU)

    assert law.title == "Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos."
    assert law.boe_updated_at == "20260430T073359Z"
    assert law.url == "https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003"
    assert law.in_force


@pytest.mark.parametrize(
    ("flag", "value"),
    [("estatus_derogacion", "S"), ("vigencia_agotada", "S")],
)
def test_reports_a_law_that_is_no_longer_in_force(flag: str, value: str) -> None:
    payload = metadata("lau_metadatos.json")
    payload["data"][0][flag] = value

    assert not parse_metadata(payload, LAU).in_force


def test_rejects_a_metadata_response_that_carries_no_data() -> None:
    with pytest.raises(ValueError, match="no data"):
        parse_metadata({"status": {"code": "404"}, "data": []}, LAU)


async def test_asks_for_xml_because_the_text_endpoint_refuses_json() -> None:
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen.update({"accept": request.headers["accept"], "url": str(request.url)})
        return httpx.Response(200, content=xml("lau_texto.xml"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        articles = await fetch_articles(LAU, client=client, today=TODAY)

    assert seen["accept"] == "application/xml"
    assert seen["url"].endswith(f"/id/{LAU}/texto")
    assert len(articles) == 2


async def test_asks_for_json_on_the_metadata_endpoint_which_does_support_it() -> None:
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["accept"] = request.headers["accept"]
        return httpx.Response(200, json=metadata("lau_metadatos.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        law = await fetch_metadata(LAU, client=client)

    assert seen["accept"] == "application/json"
    assert law.source_id == LAU


async def test_a_failing_download_is_raised_not_swallowed() -> None:
    def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_articles(LAU, client=client, today=TODAY)


async def test_a_borrowed_client_survives_the_call() -> None:
    def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml("lau_texto.xml"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await fetch_articles(LAU, client=client, today=TODAY)

        assert not client.is_closed
        await fetch_articles(CATALONIA, client=client, today=TODAY)
