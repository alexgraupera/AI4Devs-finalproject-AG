"""`make ingest`: build the corpus in the database, and say what changed.

    python -m app.ingestion
    python -m app.ingestion --force
    python -m app.ingestion --source BOE-A-1994-26003

Re-running it is a no-op when the BOE has not moved, so it is safe to run whenever in doubt.
"""

import argparse
import asyncio
import sys

from app.config import get_settings
from app.foundation.persistence.database import create_engine, session_factory
from app.ingestion.drift import write_lock
from app.ingestion.pipeline import IngestionReport, ingest
from app.ingestion.sources import CORPUS, source_by_id


def render(report: IngestionReport) -> str:
    lines = [
        "| Source | Version | Written | Updated | Unchanged | Deleted | Items | Rejected |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in report.sources:
        if entry.failed:
            lines.append(f"| `{entry.source.source_id}` | ❌ {entry.error} |")
        elif entry.skipped:
            lines.append(f"| `{entry.source.source_id}` | {entry.boe_updated_at} | _unchanged in the BOE, skipped_ |")
        else:
            diff = entry.diff
            quality = entry.quality
            assert diff is not None and quality is not None
            lines.append(
                f"| `{entry.source.source_id}` | {entry.boe_updated_at} | {diff.written} | {diff.updated} "
                f"| {diff.unchanged} | {diff.deleted} | {quality.kept} | {len(quality.rejected)} |"
            )
    return "\n".join(lines)


async def run(source_ids: list[str], *, force: bool) -> IngestionReport:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured: there is nowhere to ingest the corpus.")

    engine = create_engine(settings.database_url)
    try:
        return await ingest(
            tuple(source_by_id(source_id) for source_id in source_ids) if source_ids else CORPUS,
            session_factory=session_factory(engine),
            corpus_version=settings.corpus_version,
            max_chars=settings.chunk_max_chars,
            force=force,
        )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the BOE corpus into the vector store.")
    parser.add_argument("--source", action="append", default=[], help="Limit the ingestion to these source ids")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if the BOE version has not changed")
    arguments = parser.parse_args()

    report = asyncio.run(run(arguments.source, force=arguments.force))
    print(render(report))

    # The lock file states what the corpus was built from, so the drift check has something to
    # compare against. A partial run must not claim the sources it never looked at.
    if not arguments.source and not report.failed:
        write_lock(report.versions)

    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
