# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""Read a quarterly BOE resolution listing newly declared stressed residential areas (zonas tensionadas).

Usage:
    uv run docs/data-sources/examples/boe_stressed_areas.py                   # BOE-A-2026-16532
    uv run docs/data-sources/examples/boe_stressed_areas.py BOE-A-2025-8636
"""

import re
import sys
import xml.etree.ElementTree as ET

import httpx


def fetch_resolution(boe_id: str) -> tuple[str, str, list[str]]:
    """Returns the title, the publication date and the text paragraphs of a BOE daily item."""
    response = httpx.get("https://www.boe.es/diario_boe/xml.php", params={"id": boe_id}, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    title = root.findtext("metadatos/titulo", "")
    published = root.findtext("metadatos/fecha_publicacion", "")
    paragraphs = [" ".join("".join(p.itertext()).split()) for p in root.iter("p")]
    return title, published, [p for p in paragraphs if p]


if __name__ == "__main__":
    boe_id = sys.argv[1] if len(sys.argv) > 1 else "BOE-A-2026-16532"
    title, published, paragraphs = fetch_resolution(boe_id)
    print(f"{boe_id} · published {published}\n{title}\n")

    # Free text: extracting the area is best effort, which is why this source feeds the RAG corpus, not a tool.
    # Every declaration is listed as "– Resolución/Orden de <date>, ... por la que se declara <area> como zona...".
    # The same declarations are repeated later as "– Declaración: ..." followed by "– Memoria: <url>".
    declarations = [p.removeprefix("– ") for p in paragraphs if re.match(r"^– (Resolución|Orden|Decreto) ", p)]
    print(f"{len(declarations)} declarations in this resolution:")
    for declaration in declarations:
        area = re.search(r"por la que se declara[n]? (.+?) como zona", declaration)
        print(" -", area.group(1) if area else declaration[:160])
