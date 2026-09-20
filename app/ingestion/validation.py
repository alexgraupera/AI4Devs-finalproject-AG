"""Validation of the parsed corpus, and the report that makes it reviewable.

Two different failures, handled differently on purpose:

- **A bad item** (no text, no title, no date in force) is dropped and counted. A law with a
  handful of odd blocks is still a law worth having.
- **A bad source** (repealed, or with nothing left in force) raises. Ingesting a repealed law
  is not a data quality statistic: it is an assistant citing rules that no longer apply.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.ingestion.boe.consolidated import LawMetadata, ParsedArticle
from app.ingestion.boe.resolutions import StressedAreaDeclaration
from app.ingestion.sources import Source

EMPTY_TEXT = "empty_text"
MISSING_TITLE = "missing_title"
MISSING_FECHA_VIGENCIA = "missing_fecha_vigencia"


class RepealedSource(Exception):
    """The source is no longer in force, so it has no business being in the corpus."""


class Item(Protocol):
    """What the report needs from an article or a declaration: an identity and some text.

    Read-only members on purpose: the parsed items are frozen dataclasses, and a protocol
    asking for mutable attributes would not match them.
    """

    @property
    def block_id(self) -> str: ...

    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class Rejection:
    block_id: str
    reason: str


@dataclass(frozen=True)
class QualityReport:
    source_id: str
    parsed: int
    characters: int
    p50_chars: int
    p95_chars: int
    max_chars: int
    longest_block_id: str
    rejected: list[Rejection] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return self.parsed - len(self.rejected)


def ensure_in_force(metadata: LawMetadata) -> None:
    if not metadata.in_force:
        raise RepealedSource(
            f"{metadata.source_id} is not in force (repealed: {metadata.repealed}, exhausted: {metadata.exhausted})"
        )


def validate_articles(source: Source, articles: list[ParsedArticle]) -> tuple[list[ParsedArticle], QualityReport]:
    kept, rejected = [], []
    for article in articles:
        reason = _article_rejection(article)
        if reason is None:
            kept.append(article)
        else:
            rejected.append(Rejection(block_id=article.block_id, reason=reason))
    return kept, _report(source.source_id, parsed=len(articles), kept=kept, rejected=rejected)


def validate_declarations(
    source: Source, declarations: list[StressedAreaDeclaration]
) -> tuple[list[StressedAreaDeclaration], QualityReport]:
    kept, rejected = [], []
    for declaration in declarations:
        if declaration.text.strip():
            kept.append(declaration)
        else:
            rejected.append(Rejection(block_id=declaration.block_id, reason=EMPTY_TEXT))
    return kept, _report(source.source_id, parsed=len(declarations), kept=kept, rejected=rejected)


def _article_rejection(article: ParsedArticle) -> str | None:
    if not article.text.strip():
        return EMPTY_TEXT
    if not article.article_title.strip():
        return MISSING_TITLE
    if not article.fecha_vigencia:
        return MISSING_FECHA_VIGENCIA
    return None


def _report(source_id: str, *, parsed: int, kept: Sequence[Item], rejected: list[Rejection]) -> QualityReport:
    sizes = sorted(len(item.text) for item in kept)
    longest = max(kept, key=lambda item: len(item.text), default=None)
    return QualityReport(
        source_id=source_id,
        parsed=parsed,
        characters=sum(sizes),
        p50_chars=percentile(sizes, 50),
        p95_chars=percentile(sizes, 95),
        max_chars=sizes[-1] if sizes else 0,
        longest_block_id=longest.block_id if longest is not None else "",
        rejected=rejected,
    )


def percentile(sorted_sizes: list[int], percent: int) -> int:
    """Nearest-rank percentile: with a handful of articles, interpolating would invent precision."""
    if not sorted_sizes:
        return 0
    rank = max(1, -(-percent * len(sorted_sizes) // 100))
    return sorted_sizes[rank - 1]
