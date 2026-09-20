"""Has the BOE moved since the corpus was built?

An out-of-date corpus does not break anything, which is the problem: the assistant answers with
the old wording while citing a BOE page that shows the new one, so the failure is invisible to
everyone except the person who opens the link. Nobody is going to notice that by accident.

This check asks only `/metadatos` (5 KB and ~280 ms for the whole corpus) and compares it with
`corpus.lock.json`, the versions the corpus was last built from. It needs no database, which is
what lets it run in CI on a schedule.

    python -m app.ingestion.drift     # exit code 1 when a source moved
"""

import asyncio
import json
import pathlib
import sys
from dataclasses import dataclass

import httpx

from app.ingestion.boe import consolidated
from app.ingestion.http import borrowed_or_own
from app.ingestion.sources import CORPUS, DocType, Source

LOCK_FILE = pathlib.Path("corpus.lock.json")


@dataclass(frozen=True)
class Drift:
    source: Source
    locked: str
    live: str

    @property
    def is_new(self) -> bool:
        return not self.locked


def read_lock(path: pathlib.Path = LOCK_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    locked: dict[str, str] = json.loads(path.read_text(encoding="utf-8")).get("sources", {})
    return locked


def write_lock(versions: dict[str, str], path: pathlib.Path = LOCK_FILE) -> None:
    document = {
        "_comment": "BOE versions the corpus was built from. Written by `make ingest`, read by `make corpus-drift`.",
        "sources": versions,
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def check_drift(
    sources: tuple[Source, ...] = CORPUS,
    *,
    locked: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[Drift]:
    versions = read_lock() if locked is None else locked
    drifts = []
    async with borrowed_or_own(client) as http:
        for source in sources:
            # Resolutions are daily items with no metadata endpoint, and they are never amended:
            # what changes is that a new one is published, which no check can discover on its own.
            if source.doc_type != DocType.CONSOLIDATED_LAW:
                continue
            metadata = await consolidated.fetch_metadata(source.source_id, client=http)
            if versions.get(source.source_id, "") != metadata.boe_updated_at:
                drifts.append(
                    Drift(source=source, locked=versions.get(source.source_id, ""), live=metadata.boe_updated_at)
                )
    return drifts


def render(drifts: list[Drift]) -> str:
    if not drifts:
        return "The corpus is up to date with the BOE."

    lines = ["The BOE moved. These sources need a re-ingestion (`make ingest`):", ""]
    lines += [
        "| Source | Title | In the corpus | In the BOE |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{drift.source.source_id}` | {drift.source.title} | {drift.locked or 'never ingested'} | {drift.live} |"
        for drift in drifts
    ]
    return "\n".join(lines)


def main() -> int:
    drifts = asyncio.run(check_drift())
    print(render(drifts))
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
