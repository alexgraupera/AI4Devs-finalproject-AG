"""How a review is scored against an annotated listing: legal findings only, by law and article.

Only **legal** findings are scored. Which article a listing breaks is a fact the annotation can state;
whether a description is "too vague" is an opinion, and scoring opinions rewards the review that
says the most. A legal finding is identified by its law and article, not its paragraph or wording:
"LAU art. 36.1", "art. 36 de la LAU" and "Ley 29/1994, artículo 36" are the same finding.

| Metric | Over |
|---|---|
| precision, recall, F1 | legal findings, across the listings that must be reviewed |
| clean false positives | clean listings that received any legal finding |
| verdict accuracy | the listings that must be reviewed |
| adversarial handled | the listings that must be refused, refused with the expected reason |
| dropped | findings a check removed before the user saw them (see below) |

Dropped: the pipeline's output guardrail drops a legal basis outside its checklist; the agent drops
what its critic, evidence and citation checks do not back.
"""

import re
from dataclasses import dataclass, field

from benchmarks.retrieval.metrics import percentile

LegalRef = tuple[str, str]

_LAWS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(lau|ley\s*29/1994|arrendamientos\s+urbanos)\b", re.IGNORECASE), "LAU"),
    (re.compile(r"\b(rd|real\s+decreto)\s*390/2021\b", re.IGNORECASE), "RD 390/2021"),
    (re.compile(r"\bley\s*12/2023\b", re.IGNORECASE), "Ley 12/2023"),
    (re.compile(r"\bley\s*18/2007\b", re.IGNORECASE), "Ley 18/2007"),
]
_ARTICLE = re.compile(r"\bart(?:[íi]culo|\.)?\s*(\d+)", re.IGNORECASE)
# The BOE ids the corpus uses, for findings that carry citations instead of a readable basis.
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
    law = _BOE_LAWS.get(law_id)
    article = _ARTICLE.search(article_title)
    return (law, article.group(1)) if law and article else None


@dataclass
class ListingOutcome:
    id: str
    tags: list[str]
    expected: set[LegalRef]
    expected_verdict: str | None
    expected_error: str | None
    found: set[LegalRef] = field(default_factory=set)
    verdict: str | None = None
    error: str | None = None
    escalated: bool = False
    cost_usd: float = 0.0
    latency_ms: int = 0
    dropped: int = 0
    # Every legal finding as the review wrote it, to read the ones outside the annotation.
    notes: list[tuple[LegalRef, str]] = field(default_factory=list)
    # The agent's steps (tool, arguments, result), to tell a search that missed from a critic that rejected.
    trace: list[dict[str, object]] = field(default_factory=list)

    @property
    def must_refuse(self) -> bool:
        return self.expected_error is not None

    @property
    def is_clean(self) -> bool:
        return "clean" in self.tags


@dataclass(frozen=True)
class ListingMetrics:
    reviews: int
    precision: float
    recall: float
    f1: float
    # None when the run had no listing of that kind (a subset run with --only).
    clean_false_positive_rate: float | None
    verdict_accuracy: float
    adversarial_handled: float | None
    escalation_rate: float
    dropped_findings: int
    failures: int
    cost_per_review_usd: float
    p50_latency_ms: float
    p95_latency_ms: float


def _share(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _share_or_none(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def summarise(outcomes: list[ListingOutcome]) -> ListingMetrics:
    reviewed = [o for o in outcomes if not o.must_refuse]
    refused = [o for o in outcomes if o.must_refuse]
    true_positives = sum(len(o.found & o.expected) for o in reviewed)
    predicted = sum(len(o.found) for o in reviewed)
    expected = sum(len(o.expected) for o in reviewed)
    precision = true_positives / predicted if predicted else 1.0
    recall = true_positives / expected if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    completed = [o for o in reviewed if o.error is None]
    latencies = [float(o.latency_ms) for o in outcomes if o.error is None]
    return ListingMetrics(
        reviews=len(outcomes),
        precision=precision,
        recall=recall,
        f1=f1,
        clean_false_positive_rate=_share_or_none([bool(o.found) for o in reviewed if o.is_clean]),
        verdict_accuracy=_share([o.verdict == o.expected_verdict for o in reviewed]),
        adversarial_handled=_share_or_none([o.error == o.expected_error for o in refused]),
        escalation_rate=_share([o.escalated for o in completed]),
        dropped_findings=sum(o.dropped for o in outcomes),
        failures=sum(1 for o in reviewed if o.error is not None),
        cost_per_review_usd=sum(o.cost_usd for o in outcomes) / len(outcomes) if outcomes else 0.0,
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
    )
