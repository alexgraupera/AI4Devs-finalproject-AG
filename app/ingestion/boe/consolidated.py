"""Client for the BOE consolidated legislation API.

Parsing is separated from downloading on purpose: `parse_articles` is a pure function over the
XML, so the whole parser is tested against real saved responses without touching the network.

The rules implemented here are the ones documented in `docs/data-sources/boe-legislation.md`,
and each one exists because the API bites otherwise:

- the text endpoints answer HTTP 400 to `Accept: application/json`, so XML is not a preference
- a block keeps every historical version, and the last one is not always the one in force
- only `precepto` blocks are articles: preamble, headings, initial notes and the signature are not
- block ids are not article numbers, so the number is read from the title
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import httpx

from app.ingestion.http import borrowed_or_own
from app.ingestion.normalize import normalize

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{source_id}"
CITATION = "https://www.boe.es/buscar/act.php?id={source_id}#{block_id}"

METADATA_TIMEOUT_SECONDS = 30
TEXT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class LawMetadata:
    source_id: str
    title: str
    # `fecha_actualizacion` of the consolidated text: what decides whether to re-ingest.
    boe_updated_at: str
    url: str
    repealed: bool
    # Not repealed, but with nothing left in force. Both mean "do not ingest", for different reasons.
    exhausted: bool

    @property
    def in_force(self) -> bool:
        return not self.repealed and not self.exhausted


@dataclass(frozen=True)
class ParsedArticle:
    block_id: str
    article_title: str
    text: str
    fecha_vigencia: str
    # The norm that introduced this wording: what lets an answer say "as amended by".
    id_norma: str
    citation_url: str


def parse_metadata(payload: dict[str, object], source_id: str) -> LawMetadata:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError(f"{source_id}: the metadata response carries no data")
    metadata = data[0]
    if not isinstance(metadata, dict):
        raise ValueError(f"{source_id}: unexpected metadata shape")

    def field(name: str) -> str:
        value = metadata.get(name, "")
        return value if isinstance(value, str) else ""

    return LawMetadata(
        source_id=source_id,
        title=normalize(field("titulo")),
        boe_updated_at=field("fecha_actualizacion"),
        url=field("url_html_consolidada") or f"https://www.boe.es/buscar/act.php?id={source_id}",
        repealed=field("estatus_derogacion") == "S",
        exhausted=field("vigencia_agotada") == "S",
    )


def version_in_force(block: ET.Element, today: str) -> ET.Element | None:
    """The latest version already in force, which is not always the last one in the document."""
    versions = [v for v in block.findall("version") if v.get("fecha_vigencia", "") <= today]
    return max(versions, key=lambda v: v.get("fecha_vigencia", ""), default=None)


def parse_articles(xml: bytes, source_id: str, today: str | None = None) -> list[ParsedArticle]:
    root = ET.fromstring(xml)
    on = today or date.today().strftime("%Y%m%d")

    articles = []
    for block in root.iter("bloque"):
        if block.get("tipo") != "precepto":
            continue
        version = version_in_force(block, on)
        if version is None:
            # Every version of this block is dated in the future: it is not law yet.
            continue
        block_id = block.get("id", "")
        paragraphs = [normalize("".join(p.itertext())) for p in version.findall("p")]
        articles.append(
            ParsedArticle(
                block_id=block_id,
                article_title=normalize(block.get("titulo", "")),
                text="\n".join(p for p in paragraphs if p),
                fecha_vigencia=version.get("fecha_vigencia", ""),
                id_norma=version.get("id_norma", ""),
                citation_url=CITATION.format(source_id=source_id, block_id=block_id),
            )
        )
    return articles


async def fetch_metadata(source_id: str, *, client: httpx.AsyncClient | None = None) -> LawMetadata:
    async with borrowed_or_own(client) as http:
        response = await http.get(
            f"{API.format(source_id=source_id)}/metadatos",
            headers={"Accept": "application/json"},
            timeout=METADATA_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    return parse_metadata(response.json(), source_id)


async def fetch_articles(
    source_id: str, *, client: httpx.AsyncClient | None = None, today: str | None = None
) -> list[ParsedArticle]:
    async with borrowed_or_own(client) as http:
        response = await http.get(
            f"{API.format(source_id=source_id)}/texto",
            # Not a preference: the text endpoints answer 400 to anything else.
            headers={"Accept": "application/xml"},
            timeout=TEXT_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    return parse_articles(response.content, source_id, today)
