# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""Download a consolidated law from the BOE open data API and print its articles in force.

Usage:
    uv run docs/data-sources/examples/boe_consolidated_law.py                     # LAU, article 36
    uv run docs/data-sources/examples/boe_consolidated_law.py BOE-A-2023-12203 "Artículo 31"
"""

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import httpx

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{law_id}"


@dataclass
class Article:
    law_id: str
    block_id: str
    title: str  # e.g. "Artículo 36" (block ids do not always match the article number)
    text: str  # text of the version in force
    in_force_since: str  # YYYYMMDD
    amended_by: str  # id of the norm that introduced this version
    url: str


def fetch_metadata(law_id: str) -> dict:
    # Metadata supports JSON; the text endpoints only support XML.
    response = httpx.get(API.format(law_id=law_id) + "/metadatos", headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()["data"][0]


def normalize(text: str) -> str:
    # The BOE mixes regular and non-breaking spaces ("Artículo\xa031"): collapse every whitespace.
    return " ".join(text.split())


def version_in_force(block: ET.Element, today: str) -> ET.Element | None:
    # A block keeps every historical version. Pick the latest one already in force.
    versions = [v for v in block.findall("version") if v.get("fecha_vigencia", "") <= today]
    return max(versions, key=lambda v: v.get("fecha_vigencia", ""), default=None)


def fetch_articles(law_id: str) -> list[Article]:
    response = httpx.get(API.format(law_id=law_id) + "/texto", headers={"Accept": "application/xml"}, timeout=60)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    today = date.today().strftime("%Y%m%d")
    articles = []
    for block in root.iter("bloque"):
        if block.get("tipo") != "precepto":  # skip preamble, titles, chapters...
            continue
        version = version_in_force(block, today)
        if version is None:
            continue
        paragraphs = [normalize("".join(p.itertext())) for p in version.findall("p")]
        articles.append(
            Article(
                law_id=law_id,
                block_id=block.get("id", ""),
                title=normalize(block.get("titulo", "")),
                text="\n".join(p for p in paragraphs if p),
                in_force_since=version.get("fecha_vigencia", ""),
                amended_by=version.get("id_norma", ""),
                url=f"https://www.boe.es/buscar/act.php?id={law_id}#{block.get('id')}",
            )
        )
    return articles


if __name__ == "__main__":
    law_id = sys.argv[1] if len(sys.argv) > 1 else "BOE-A-1994-26003"
    wanted = sys.argv[2] if len(sys.argv) > 2 else "Artículo 36"

    metadata = fetch_metadata(law_id)
    print(
        f"{metadata['titulo']} (updated {metadata['fecha_actualizacion']}, repealed: {metadata['estatus_derogacion']})"
    )

    articles = fetch_articles(law_id)
    print(f"{len(articles)} articles in force, {sum(len(a.text) for a in articles):,} characters\n")

    article = next(a for a in articles if a.title == wanted)
    print(f"[{article.block_id}] {article.title} · in force since {article.in_force_since} ({article.amended_by})")
    print(article.url)
    print(article.text[:600], "...")
