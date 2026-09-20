"""What the corpus is made of.

One place answers "which norms does the assistant know about", so adding a regional law is a
line here plus a row in the data-source guide, not a search through the ingestion code.

Every source was validated against the live API on 2026-09-20 and is documented in
`docs/data-sources/`: the identifiers here are not guesses.
"""

from dataclasses import dataclass
from enum import StrEnum


class Jurisdiction(StrEnum):
    STATE = "state"
    CATALONIA = "catalonia"


class DocType(StrEnum):
    CONSOLIDATED_LAW = "consolidated_law"
    RESOLUTION = "resolution"


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    jurisdiction: Jurisdiction
    doc_type: DocType


CORPUS: tuple[Source, ...] = (
    Source(
        source_id="BOE-A-1994-26003",
        title="Ley 29/1994, de Arrendamientos Urbanos",
        jurisdiction=Jurisdiction.STATE,
        doc_type=DocType.CONSOLIDATED_LAW,
    ),
    Source(
        source_id="BOE-A-2023-12203",
        title="Ley 12/2023, por el derecho a la vivienda",
        jurisdiction=Jurisdiction.STATE,
        doc_type=DocType.CONSOLIDATED_LAW,
    ),
    Source(
        source_id="BOE-A-2021-9176",
        title="Real Decreto 390/2021, certificado de eficiencia energética",
        jurisdiction=Jurisdiction.STATE,
        doc_type=DocType.CONSOLIDATED_LAW,
    ),
    # Regional, and served by the same consolidated API as the state laws: same parser, one
    # more jurisdiction to filter by. Its article 61 governs what a rental offer must state.
    Source(
        source_id="BOE-A-2008-3657",
        title="Ley 18/2007, del derecho a la vivienda (Cataluña)",
        jurisdiction=Jurisdiction.CATALONIA,
        doc_type=DocType.CONSOLIDATED_LAW,
    ),
    # Daily items, not consolidated legislation: a different endpoint and a different parser.
    Source(
        source_id="BOE-A-2026-16532",
        title="Zonas de mercado residencial tensionado (2T 2026)",
        jurisdiction=Jurisdiction.STATE,
        doc_type=DocType.RESOLUTION,
    ),
    Source(
        source_id="BOE-A-2025-8636",
        title="Zonas de mercado residencial tensionado (1T 2025)",
        jurisdiction=Jurisdiction.STATE,
        doc_type=DocType.RESOLUTION,
    ),
)


def source_by_id(source_id: str) -> Source:
    for source in CORPUS:
        if source.source_id == source_id:
            return source
    raise KeyError(f"{source_id} is not part of the corpus")
