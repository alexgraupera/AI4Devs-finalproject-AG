import json
import pathlib

import httpx

from app.ingestion.drift import check_drift, read_lock, render, write_lock
from app.ingestion.sources import source_by_id
from tests.ingestion.fixtures import LAU, metadata

LAWS = (source_by_id(LAU),)
RESOLUTION = source_by_id("BOE-A-2025-8636")


def serving_metadata(updated_at: str) -> httpx.AsyncClient:
    payload = metadata("lau_metadatos.json")
    payload["data"][0]["fecha_actualizacion"] = updated_at

    def respond(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(respond))


async def test_says_nothing_when_the_corpus_matches_the_boe() -> None:
    async with serving_metadata("20260430T073359Z") as client:
        drifts = await check_drift(LAWS, locked={LAU: "20260430T073359Z"}, client=client)

    assert drifts == []


async def test_reports_a_law_the_boe_has_updated() -> None:
    async with serving_metadata("20261001T000000Z") as client:
        drifts = await check_drift(LAWS, locked={LAU: "20260430T073359Z"}, client=client)

    assert len(drifts) == 1
    assert (drifts[0].locked, drifts[0].live) == ("20260430T073359Z", "20261001T000000Z")
    assert not drifts[0].is_new


async def test_reports_a_source_that_was_never_ingested() -> None:
    async with serving_metadata("20260430T073359Z") as client:
        drifts = await check_drift(LAWS, locked={}, client=client)

    assert drifts[0].is_new


async def test_does_not_ask_about_resolutions_which_have_no_version_to_compare() -> None:
    calls = 0

    def respond(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=metadata("lau_metadatos.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await check_drift((RESOLUTION,), locked={}, client=client)

    assert calls == 0


def test_the_lock_file_survives_a_write_and_a_read(tmp_path: pathlib.Path) -> None:
    lock = tmp_path / "corpus.lock.json"

    write_lock({LAU: "20260430T073359Z"}, lock)

    assert read_lock(lock) == {LAU: "20260430T073359Z"}
    assert json.loads(lock.read_text())["sources"] == {LAU: "20260430T073359Z"}


def test_a_missing_lock_file_means_nothing_was_ingested_yet(tmp_path: pathlib.Path) -> None:
    assert read_lock(tmp_path / "absent.json") == {}


async def test_the_report_names_the_sources_to_reingest() -> None:
    async with serving_metadata("20261001T000000Z") as client:
        output = render(await check_drift(LAWS, locked={LAU: "20260430T073359Z"}, client=client))

    assert "make ingest" in output
    assert LAU in output
    assert "20261001T000000Z" in output


def test_the_report_is_quiet_when_there_is_nothing_to_do() -> None:
    assert render([]) == "The corpus is up to date with the BOE."
