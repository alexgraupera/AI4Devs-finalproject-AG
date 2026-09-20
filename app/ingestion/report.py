"""`make corpus-report`: download the corpus, validate it and print what came back.

It writes nothing. The question this command answers is "is the corpus what the data-source
guides say it is?", and it is worth answering before deciding how to cut the documents up and
long before spending money embedding them.

    python -m app.ingestion.report
    python -m app.ingestion.report --source BOE-A-1994-26003
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

import httpx

from app.ingestion.boe import consolidated, resolutions
from app.ingestion.sources import CORPUS, DocType, Source, source_by_id
from app.ingestion.validation import (
    QualityReport,
    RepealedSource,
    ensure_in_force,
    validate_articles,
    validate_declarations,
)


@dataclass(frozen=True)
class SourceReport:
    source: Source
    report: QualityReport | None
    updated_at: str = ""
    error: str = ""

    @property
    def failed(self) -> bool:
        return self.report is None


async def inspect(source: Source, client: httpx.AsyncClient) -> SourceReport:
    try:
        if source.doc_type == DocType.RESOLUTION:
            declarations = await resolutions.fetch_declarations(source.source_id, client=client)
            _, report = validate_declarations(source, declarations)
            return SourceReport(source=source, report=report)

        metadata = await consolidated.fetch_metadata(source.source_id, client=client)
        ensure_in_force(metadata)
        articles = await consolidated.fetch_articles(source.source_id, client=client)
        _, report = validate_articles(source, articles)
        return SourceReport(source=source, report=report, updated_at=metadata.boe_updated_at)
    except (httpx.HTTPError, RepealedSource, ValueError) as error:
        # One unreachable source must not hide the state of the other five.
        return SourceReport(source=source, report=None, error=f"{type(error).__name__}: {error}")


async def inspect_all(sources: tuple[Source, ...]) -> list[SourceReport]:
    async with httpx.AsyncClient() as client:
        return [await inspect(source, client) for source in sources]


def render(reports: list[SourceReport]) -> str:
    lines = [
        "| Source | Jurisdiction | Items | Kept | Rejected | Characters | p50 | p95 | Max | Longest | Updated |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for entry in reports:
        if entry.report is None:
            lines.append(f"| `{entry.source.source_id}` | {entry.source.jurisdiction} | ❌ {entry.error} |")
            continue
        report = entry.report
        lines.append(
            f"| `{report.source_id}` | {entry.source.jurisdiction} | {report.parsed} | {report.kept} "
            f"| {len(report.rejected)} | {report.characters:,} | {report.p50_chars:,} | {report.p95_chars:,} "
            f"| {report.max_chars:,} | `{report.longest_block_id}` | {entry.updated_at or '-'} |"
        )

    rejections = [
        f"- `{entry.source.source_id}` `{rejection.block_id}`: {rejection.reason}"
        for entry in reports
        if entry.report is not None
        for rejection in entry.report.rejected
    ]
    if rejections:
        lines += ["", "**Rejected items**", *rejections]

    kept = sum(entry.report.kept for entry in reports if entry.report is not None)
    characters = sum(entry.report.characters for entry in reports if entry.report is not None)
    lines += ["", f"**Total**: {kept} items, {characters:,} characters (~{characters // 4:,} tokens)"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the BOE corpus and report its quality. Writes nothing.")
    parser.add_argument("--source", action="append", default=[], help="Limit the report to these source ids")
    arguments = parser.parse_args()

    sources = tuple(source_by_id(source_id) for source_id in arguments.source) if arguments.source else CORPUS
    reports = asyncio.run(inspect_all(sources))
    print(render(reports))
    return 1 if any(entry.failed for entry in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
