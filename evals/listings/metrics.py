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

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.legal_refs import LegalRef
from benchmarks.retrieval.metrics import percentile


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
    # From the agent's trace: the articles it read, and the ones whose findings its critic rejected.
    read: set[LegalRef] = field(default_factory=set)
    rejected: list[tuple[LegalRef | None, str]] = field(default_factory=list)
    stop_reason: str | None = None
    tool_errors: int = 0
    # Cost by step (plan, tools, critic, rewrite) for the agent; one `review` step for the pipeline.
    step_costs: dict[str, float] = field(default_factory=dict)
    repeat: int = 1

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


class Failure(StrEnum):
    """Why a listing was reviewed wrong, from the outcome and the agent's trace (#52).

    An expected article the agent missed is placed in the first step that lost it: never read
    (the search), read but not reported (the actor), reported but rejected (the critic). The
    pipeline has no trace, so its misses are only missed.
    """

    NOT_READ = "not_read"
    READ_NOT_REPORTED = "read_not_reported"
    REJECTED_BY_CRITIC = "rejected_by_critic"
    MISSED = "missed"
    INVENTED = "invented"
    WRONG_VERDICT = "wrong_verdict"
    NOT_REFUSED = "not_refused"
    RUN_FAILED = "run_failed"


def classify(outcome: ListingOutcome, *, traced: bool) -> list[Failure]:
    if outcome.must_refuse:
        return [] if outcome.error == outcome.expected_error else [Failure.NOT_REFUSED]
    if outcome.error is not None:
        return [Failure.RUN_FAILED]
    rejected = {ref for ref, _ in outcome.rejected if ref is not None}
    failures = []
    for ref in sorted(outcome.expected - outcome.found):
        if not traced:
            failures.append(Failure.MISSED)
        elif ref in rejected:
            failures.append(Failure.REJECTED_BY_CRITIC)
        elif ref in outcome.read:
            failures.append(Failure.READ_NOT_REPORTED)
        else:
            failures.append(Failure.NOT_READ)
    failures += [Failure.INVENTED] * len(outcome.found - outcome.expected)
    if outcome.verdict != outcome.expected_verdict:
        failures.append(Failure.WRONG_VERDICT)
    return failures


def failure_counts(outcomes: list[ListingOutcome], *, traced: bool) -> Counter[Failure]:
    return Counter(failure for outcome in outcomes for failure in classify(outcome, traced=traced))
