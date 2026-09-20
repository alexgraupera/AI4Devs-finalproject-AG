"""The ingestion: from the BOE to rows, once per source, skipping what has not moved.

Two cheap checks save the expensive work, in this order:

1. `/metadatos` costs 1.3 KB and ~50 ms, and says whether the consolidated text changed at all.
   Only if it did is the full text downloaded, which for the Catalan law is 1.4 MB.
2. Within a source that did change, `content_hash` per chunk means only the articles actually
   reformed are rewritten, which from #22 onwards is also what stops a re-ingestion from paying
   to embed the whole corpus again.

One source failing does not abort the others: a BOE endpoint being down should leave five laws
ingested and one reported, not an empty corpus.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.boe import consolidated, resolutions
from app.ingestion.chunking import Chunk, chunk_article, chunk_declaration
from app.ingestion.http import borrowed_or_own
from app.ingestion.repository import ChunkDiff, replace_chunks, stored_versions, upsert_document
from app.ingestion.sources import DocType, Source
from app.ingestion.validation import (
    QualityReport,
    RepealedSource,
    ensure_in_force,
    validate_articles,
    validate_declarations,
)

log = structlog.get_logger()

INGESTION_ERRORS = (httpx.HTTPError, RepealedSource, ValueError, OSError)


@dataclass(frozen=True)
class Parsed:
    """What a source looks like once downloaded and cut up, before anything is written."""

    title: str
    url: str
    boe_updated_at: str
    chunks: list[Chunk]
    quality: QualityReport


@dataclass(frozen=True)
class SourceIngestion:
    source: Source
    boe_updated_at: str = ""
    quality: QualityReport | None = None
    diff: ChunkDiff | None = None
    skipped: bool = False
    error: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.error)


@dataclass(frozen=True)
class IngestionReport:
    sources: list[SourceIngestion]

    @property
    def failed(self) -> bool:
        return any(entry.failed for entry in self.sources)

    @property
    def versions(self) -> dict[str, str]:
        """What the corpus was built from, for the lock file the drift check reads."""
        return {
            entry.source.source_id: entry.boe_updated_at
            for entry in sorted(self.sources, key=lambda e: e.source.source_id)
            if entry.boe_updated_at and not entry.failed
        }


async def ingest(
    sources: Iterable[Source],
    *,
    session_factory: async_sessionmaker[AsyncSession],
    corpus_version: str,
    max_chars: int,
    force: bool = False,
    client: httpx.AsyncClient | None = None,
) -> IngestionReport:
    async with session_factory() as session:
        known = await stored_versions(session)

    entries = []
    async with borrowed_or_own(client) as http:
        for source in sources:
            entries.append(
                await _ingest_source(
                    source,
                    http=http,
                    session_factory=session_factory,
                    known=known,
                    corpus_version=corpus_version,
                    max_chars=max_chars,
                    force=force,
                )
            )
    return IngestionReport(sources=entries)


async def _ingest_source(
    source: Source,
    *,
    http: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    known: dict[str, str],
    corpus_version: str,
    max_chars: int,
    force: bool,
) -> SourceIngestion:
    try:
        if source.doc_type == DocType.CONSOLIDATED_LAW:
            metadata = await consolidated.fetch_metadata(source.source_id, client=http)
            ensure_in_force(metadata)
            if _unchanged(source, metadata.boe_updated_at, known=known, force=force):
                return SourceIngestion(source=source, boe_updated_at=metadata.boe_updated_at, skipped=True)
            parsed = await _read_law(source, metadata, http=http, max_chars=max_chars)
        else:
            # Daily items have no metadata endpoint, so there is no cheap version to check
            # first. They are small (14 KB), which is why that is not worth solving.
            parsed = await _read_resolution(source, http=http)
            if _unchanged(source, parsed.boe_updated_at, known=known, force=force):
                return SourceIngestion(
                    source=source, boe_updated_at=parsed.boe_updated_at, quality=parsed.quality, skipped=True
                )

        async with session_factory() as session, session.begin():
            document_id = await upsert_document(
                session,
                source,
                title=parsed.title,
                url=parsed.url,
                boe_updated_at=parsed.boe_updated_at,
                corpus_version=corpus_version,
            )
            diff = await replace_chunks(session, document_id, parsed.chunks)

        log.info(
            "ingestion.completed",
            source_id=source.source_id,
            boe_updated_at=parsed.boe_updated_at,
            written=diff.written,
            updated=diff.updated,
            unchanged=diff.unchanged,
            deleted=diff.deleted,
        )
        return SourceIngestion(source=source, boe_updated_at=parsed.boe_updated_at, quality=parsed.quality, diff=diff)
    except INGESTION_ERRORS as error:
        log.warning("ingestion.failed", source_id=source.source_id, error=str(error))
        return SourceIngestion(source=source, error=f"{type(error).__name__}: {error}")


def _unchanged(source: Source, boe_updated_at: str, *, known: dict[str, str], force: bool) -> bool:
    if force or known.get(source.source_id) != boe_updated_at:
        return False
    log.info("ingestion.skipped", source_id=source.source_id, boe_updated_at=boe_updated_at)
    return True


async def _read_law(
    source: Source, metadata: consolidated.LawMetadata, *, http: httpx.AsyncClient, max_chars: int
) -> Parsed:
    articles = await consolidated.fetch_articles(source.source_id, client=http)
    kept, quality = validate_articles(source, articles)
    chunks = [chunk for article in kept for chunk in chunk_article(article, max_chars=max_chars)]
    return Parsed(
        title=metadata.title,
        url=metadata.url,
        boe_updated_at=metadata.boe_updated_at,
        chunks=chunks,
        quality=quality,
    )


async def _read_resolution(source: Source, *, http: httpx.AsyncClient) -> Parsed:
    declarations = await resolutions.fetch_declarations(source.source_id, client=http)
    kept, quality = validate_declarations(source, declarations)
    if not kept:
        raise ValueError(f"{source.source_id}: the resolution declared no areas")
    return Parsed(
        title=source.title,
        url=kept[0].citation_url,
        # A daily item is never amended: its publication date is its version.
        boe_updated_at=kept[0].published_on,
        chunks=[chunk_declaration(declaration) for declaration in kept],
        quality=quality,
    )
