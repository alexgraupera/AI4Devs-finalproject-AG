"""Writing the corpus into the schema of #20, without rewriting what has not changed.

Idempotency is not a nicety here: re-ingesting is how the corpus is kept current, and it will
run again and again over a corpus where almost nothing moved. Comparing `content_hash` per
chunk means an unchanged article is left exactly as it was, which from #22 onwards is also what
stops a re-ingestion from paying to embed the whole corpus again.
"""

import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunking import Chunk
from app.ingestion.sources import Source


@dataclass(frozen=True)
class ChunkDiff:
    written: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0

    @property
    def touched(self) -> int:
        return self.written + self.updated + self.deleted


async def stored_versions(session: AsyncSession) -> dict[str, str]:
    """What the database was last built from: `source_id` to `boe_updated_at`."""
    rows = await session.execute(text("SELECT source_id, boe_updated_at FROM documents"))
    return {row.source_id: row.boe_updated_at for row in rows}


async def upsert_document(
    session: AsyncSession,
    source: Source,
    *,
    title: str,
    url: str,
    boe_updated_at: str,
    corpus_version: str,
) -> int:
    document_id = await session.scalar(
        text("""
            INSERT INTO documents (source_id, title, jurisdiction, doc_type, url, boe_updated_at, corpus_version)
            VALUES (:source_id, :title, :jurisdiction, :doc_type, :url, :boe_updated_at, :corpus_version)
            ON CONFLICT (source_id) DO UPDATE SET
                title = EXCLUDED.title,
                url = EXCLUDED.url,
                boe_updated_at = EXCLUDED.boe_updated_at,
                corpus_version = EXCLUDED.corpus_version,
                ingested_at = now()
            RETURNING id
        """),
        {
            "source_id": source.source_id,
            "title": title,
            "jurisdiction": source.jurisdiction.value,
            "doc_type": source.doc_type.value,
            "url": url,
            "boe_updated_at": boe_updated_at,
            "corpus_version": corpus_version,
        },
    )
    if document_id is None:
        raise RuntimeError(f"{source.source_id}: the document could not be written")
    return int(document_id)


async def replace_chunks(session: AsyncSession, document_id: int, chunks: list[Chunk]) -> ChunkDiff:
    rows = await session.execute(
        text("SELECT block_id, ordinal, content_hash FROM chunks WHERE document_id = :document_id"),
        {"document_id": document_id},
    )
    stored = {(row.block_id, row.ordinal): row.content_hash for row in rows}

    written = updated = unchanged = 0
    for chunk in chunks:
        key = (chunk.block_id, chunk.ordinal)
        if key not in stored:
            await session.execute(_INSERT_CHUNK, _parameters(document_id, chunk))
            written += 1
        elif stored[key] != chunk.content_hash:
            await session.execute(_UPDATE_CHUNK, _parameters(document_id, chunk))
            updated += 1
        else:
            unchanged += 1

    # An article that disappeared from the source (repealed, renumbered) must disappear from the
    # corpus too, or the assistant keeps citing it.
    gone = set(stored) - {(chunk.block_id, chunk.ordinal) for chunk in chunks}
    for block_id, ordinal in gone:
        await session.execute(
            text("DELETE FROM chunks WHERE document_id = :document_id AND block_id = :block_id AND ordinal = :ordinal"),
            {"document_id": document_id, "block_id": block_id, "ordinal": ordinal},
        )

    return ChunkDiff(written=written, updated=updated, unchanged=unchanged, deleted=len(gone))


_INSERT_CHUNK = text("""
    INSERT INTO chunks (document_id, block_id, article_title, ordinal, text, char_count, metadata, content_hash)
    VALUES (:document_id, :block_id, :article_title, :ordinal, :text, :char_count, :metadata, :content_hash)
""")

_UPDATE_CHUNK = text("""
    UPDATE chunks
    SET article_title = :article_title,
        text = :text,
        char_count = :char_count,
        metadata = :metadata,
        content_hash = :content_hash
    WHERE document_id = :document_id AND block_id = :block_id AND ordinal = :ordinal
""")


def _parameters(document_id: int, chunk: Chunk) -> dict[str, object]:
    return {
        "document_id": document_id,
        "block_id": chunk.block_id,
        "article_title": chunk.article_title,
        "ordinal": chunk.ordinal,
        "text": chunk.text,
        "char_count": chunk.char_count,
        "metadata": json.dumps(chunk.metadata, ensure_ascii=False),
        "content_hash": chunk.content_hash,
    }
