"""The pipeline decisions, tested with the BOE faked and the database real.

The fixtures stand in for the network, so these tests state what the pipeline does with a
source that moved, one that did not, and one that is simply down.
"""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.foundation.persistence.database import create_engine, session_factory
from app.ingestion.pipeline import ingest
from app.ingestion.sources import DocType, Jurisdiction, Source
from tests.ingestion.fixtures import metadata, xml

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is not exported: no database to write to")

# Test-only identifiers: the fixtures serve the saved responses whatever the id, and using the
# real ones would make this suite delete the corpus a developer just ingested.
A_LAW = Source(
    source_id="BOE-TEST-LAW",
    title="Ley 29/1994",
    jurisdiction=Jurisdiction.STATE,
    doc_type=DocType.CONSOLIDATED_LAW,
)
A_RESOLUTION = Source(
    source_id="BOE-TEST-RESOLUTION",
    title="Zonas tensionadas",
    jurisdiction=Jurisdiction.STATE,
    doc_type=DocType.RESOLUTION,
)


class FakeBoe:
    """Serves the saved responses, and counts what was actually asked for."""

    def __init__(self, updated_at: str = "20260430T073359Z") -> None:
        self.updated_at = updated_at
        self.calls: list[str] = []

    def client(self) -> httpx.AsyncClient:
        def respond(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.calls.append(url)
            if "/metadatos" in url:
                payload = metadata("lau_metadatos.json")
                payload["data"][0]["fecha_actualizacion"] = self.updated_at
                return httpx.Response(200, json=payload)
            if "/texto" in url:
                return httpx.Response(200, content=xml("lau_texto.xml"))
            return httpx.Response(200, content=xml("stressed_areas.xml"))

        return httpx.AsyncClient(transport=httpx.MockTransport(respond))

    @property
    def text_downloads(self) -> int:
        return len([call for call in self.calls if "/texto" in call])


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(DATABASE_URL)
    factory = session_factory(engine)
    yield factory
    async with factory() as session, session.begin():
        await session.execute(
            text("DELETE FROM documents WHERE source_id = ANY(:ids)"),
            {"ids": [A_LAW.source_id, A_RESOLUTION.source_id]},
        )
    await engine.dispose()


async def run(sources: tuple[Source, ...], boe: FakeBoe, sessions: async_sessionmaker[AsyncSession], **kwargs: object):  # type: ignore[no-untyped-def]
    async with boe.client() as client:
        return await ingest(
            sources,
            session_factory=sessions,
            corpus_version="test",
            max_chars=6_000,
            client=client,
            **kwargs,  # type: ignore[arg-type]
        )


async def test_the_first_run_writes_the_corpus(sessions: async_sessionmaker[AsyncSession]) -> None:
    report = await run((A_LAW,), FakeBoe(), sessions)

    entry = report.sources[0]
    assert not report.failed
    assert entry.diff is not None and entry.diff.written == 2
    assert entry.quality is not None and entry.quality.kept == 2


async def test_running_it_again_writes_nothing(sessions: async_sessionmaker[AsyncSession]) -> None:
    boe = FakeBoe()
    await run((A_LAW,), boe, sessions)

    second = await run((A_LAW,), boe, sessions)

    assert second.sources[0].skipped
    assert second.sources[0].diff is None


async def test_an_unchanged_law_is_not_even_downloaded(sessions: async_sessionmaker[AsyncSession]) -> None:
    # The whole point of checking the metadata first: the text of the Catalan law is 1.4 MB.
    boe = FakeBoe()
    await run((A_LAW,), boe, sessions)
    downloads_after_first = boe.text_downloads

    await run((A_LAW,), boe, sessions)

    assert downloads_after_first == 1
    assert boe.text_downloads == 1


async def test_a_reform_in_the_boe_triggers_a_reingestion(sessions: async_sessionmaker[AsyncSession]) -> None:
    boe = FakeBoe()
    await run((A_LAW,), boe, sessions)

    boe.updated_at = "20261001T000000Z"
    report = await run((A_LAW,), boe, sessions)

    entry = report.sources[0]
    assert not entry.skipped
    assert entry.diff is not None and entry.diff.unchanged == 2  # the articles themselves did not change


async def test_force_reingests_even_when_nothing_moved(sessions: async_sessionmaker[AsyncSession]) -> None:
    boe = FakeBoe()
    await run((A_LAW,), boe, sessions)

    report = await run((A_LAW,), boe, sessions, force=True)

    assert not report.sources[0].skipped
    assert boe.text_downloads == 2


async def test_a_resolution_is_ingested_as_one_chunk_per_declared_area(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    report = await run((A_RESOLUTION,), FakeBoe(), sessions)

    entry = report.sources[0]
    assert entry.diff is not None and entry.diff.written == 4
    assert entry.boe_updated_at == "20250430"


async def test_a_source_that_is_down_does_not_take_the_others_with_it(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    class BrokenLaw(FakeBoe):
        def client(self) -> httpx.AsyncClient:
            def respond(request: httpx.Request) -> httpx.Response:
                if A_LAW.source_id in str(request.url):
                    return httpx.Response(503)
                return httpx.Response(200, content=xml("stressed_areas.xml"))

            return httpx.AsyncClient(transport=httpx.MockTransport(respond))

    report = await run((A_LAW, A_RESOLUTION), BrokenLaw(), sessions)

    assert report.failed
    assert report.sources[0].failed
    assert not report.sources[1].failed
    assert report.sources[1].diff is not None and report.sources[1].diff.written == 4


async def test_a_failed_source_is_left_out_of_the_lock_file(sessions: async_sessionmaker[AsyncSession]) -> None:
    class Broken(FakeBoe):
        def client(self) -> httpx.AsyncClient:
            return httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))

    report = await run((A_LAW,), Broken(), sessions)

    assert report.versions == {}
