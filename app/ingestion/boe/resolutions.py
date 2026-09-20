"""Client for the quarterly BOE resolutions listing newly declared stressed residential areas.

These are daily BOE items, not consolidated legislation: different endpoint, different shape,
no versions to choose from.

Each resolution lists its declarations twice, first as the list of declared areas and then
again with their validity and links. Only the first list is kept: the second repeats the same
areas and would put the same fact in the corpus twice, which is how a retrieval starts
returning three chunks that say one thing.

The area is free text and can be smaller than a municipality, which is exactly why this source
feeds the corpus instead of a deterministic "is this address in a stressed area" tool: see
`docs/data-sources/boe-stressed-areas.md`.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from app.ingestion.http import borrowed_or_own
from app.ingestion.normalize import normalize

API = "https://www.boe.es/diario_boe/xml.php"
CITATION = "https://www.boe.es/diario_boe/txt.php?id={source_id}"
TIMEOUT_SECONDS = 30

# "– Resolución de 29 de abril de 2025, ... por la que se declara ... como zona de mercado
# residencial tensionado". The dash is the BOE's en dash, not a hyphen.
DECLARATION = re.compile(r"^–\s*(Resolución|Orden|Decreto|Acuerdo)\s")


@dataclass(frozen=True)
class StressedAreaDeclaration:
    source_id: str
    # Position inside the resolution: these items have no block ids, so the citation anchor and
    # the chunk identity are built from the order in which the declarations are published.
    block_id: str
    text: str
    published_on: str
    citation_url: str


def parse_declarations(xml: bytes, source_id: str) -> list[StressedAreaDeclaration]:
    root = ET.fromstring(xml)
    published_on = root.findtext("metadatos/fecha_publicacion", "") or ""
    paragraphs = [normalize("".join(p.itertext())) for p in root.iter("p")]

    declarations: list[StressedAreaDeclaration] = []
    for paragraph in paragraphs:
        if not DECLARATION.match(paragraph):
            continue
        declarations.append(
            StressedAreaDeclaration(
                source_id=source_id,
                block_id=f"d{len(declarations) + 1}",
                text=paragraph.removeprefix("– ").strip(),
                published_on=published_on,
                citation_url=CITATION.format(source_id=source_id),
            )
        )
    return declarations


async def fetch_declarations(
    source_id: str, *, client: httpx.AsyncClient | None = None
) -> list[StressedAreaDeclaration]:
    async with borrowed_or_own(client) as http:
        response = await http.get(API, params={"id": source_id}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_declarations(response.content, source_id)
