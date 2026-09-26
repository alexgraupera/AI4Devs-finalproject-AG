"""A legal basis as the law and article it names, however it is written.

"LAU art. 36.1", "art. 36 de la LAU" and "Ley 29/1994, artículo 36" are the same article. The
paragraph is not part of the reference: a finding citing article 61.2 for a rule in 61.2.c cites
the right article. Only the laws of the corpus are known; anything else is None, never a guess.
"""

import re

LegalRef = tuple[str, str]

_LAWS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(lau|ley\s*29/1994|arrendamientos\s+urbanos)\b", re.IGNORECASE), "LAU"),
    (re.compile(r"\b(rd|real\s+decreto)\s*390/2021\b", re.IGNORECASE), "RD 390/2021"),
    (re.compile(r"\bley\s*12/2023\b", re.IGNORECASE), "Ley 12/2023"),
    (re.compile(r"\bley\s*18/2007\b", re.IGNORECASE), "Ley 18/2007"),
]
_ARTICLE = re.compile(r"\bart(?:[íi]culo|\.)?\s*(\d+)", re.IGNORECASE)
# The BOE ids the corpus uses (app/ingestion/sources.py), for a fragment or a citation.
_BOE_LAWS = {
    "BOE-A-1994-26003": "LAU",
    "BOE-A-2021-9176": "RD 390/2021",
    "BOE-A-2023-12203": "Ley 12/2023",
    "BOE-A-2008-3657": "Ley 18/2007",
}


def legal_ref(basis: str | None) -> LegalRef | None:
    """("LAU", "36") from "LAU art. 36.1", or None when it names no known law and article."""
    if not basis:
        return None
    article = _ARTICLE.search(basis)
    law = next((name for pattern, name in _LAWS if pattern.search(basis)), None)
    return (law, article.group(1)) if law and article else None


def citation_ref(law_id: str, article_title: str) -> LegalRef | None:
    """("LAU", "36") from a fragment or citation of BOE-A-1994-26003 titled "Artículo 36"."""
    law = _BOE_LAWS.get(law_id)
    article = _ARTICLE.search(article_title)
    return (law, article.group(1)) if law and article else None
