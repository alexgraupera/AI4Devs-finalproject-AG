"""The numbers an answer has to move, from the golden labels first and from the judge second.

Retrieval-side metrics come free and exact from the labels (which articles the answer needed);
generation-side metrics come from the judge. Together they are the four RAGAS axes (S11), with
context precision left out on purpose: it needs every retrieved chunk labelled as relevant or not,
and the golden set labels only the articles that answer the question.

| Metric | Over | From |
|---|---|---|
| `answered_rate` | answerable questions | labels |
| `refusal_rate` | out-of-domain questions (a guardrail rejection counts as a refusal) | labels |
| `citation_accuracy` | answerable questions: an expected article among the citations | labels |
| `context_recall` | answerable questions: an expected article in the context the model read | labels |
| `faithfulness` | answered questions: share of legal claims the context supports | judge |
| `relevance` | answered questions | judge |
| `correctness` | answerable questions, a refusal scoring 0 | judge |
| `opening_consistency` | answered questions: the first sentence survives the rest | judge |
"""

from dataclasses import dataclass, field

from benchmarks.retrieval.metrics import percentile
from evals.answers.judge import Judged


@dataclass
class AnswerOutcome:
    id: str
    question: str
    tags: list[str]
    expected: list[str]
    answered: bool
    answer: str = ""
    cited: list[str] = field(default_factory=list)
    in_context: list[str] = field(default_factory=list)
    rejected_by: str | None = None
    error: str | None = None
    judged: Judged | None = None
    cost_by_stage: dict[str, float] = field(default_factory=dict)
    latency_ms: int = 0

    @property
    def answerable(self) -> bool:
        return bool(self.expected)

    @property
    def is_regression(self) -> bool:
        return "regression" in self.tags

    @property
    def cites_expected(self) -> bool:
        return bool(set(self.expected) & set(self.cited))

    @property
    def service_cost(self) -> float:
        """What the answer cost the service; the judge's call is the evaluation's cost, not the product's."""
        return sum(cost for stage, cost in self.cost_by_stage.items() if stage != "eval_judge")


@dataclass(frozen=True)
class AnswerMetrics:
    questions: int
    answered_rate: float
    refusal_rate: float
    citation_accuracy: float
    context_recall: float
    faithfulness: float
    relevance: float
    correctness: float
    opening_consistency: float
    regressions_passed: int
    regressions: int
    cost_per_question_usd: float
    cost_by_stage_usd: dict[str, float]
    p50_latency_ms: float
    p95_latency_ms: float


def _share(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def regression_passed(outcome: AnswerOutcome) -> bool:
    """A regression case passes only if the bug it was written for stays fixed and the answer is right."""
    judged = outcome.judged
    return (
        outcome.answered
        and outcome.cites_expected
        and judged is not None
        and judged.opening_holds
        and judged.correctness >= 0.5
    )


def summarise(outcomes: list[AnswerOutcome]) -> AnswerMetrics:
    answerable = [o for o in outcomes if o.answerable]
    out_of_domain = [o for o in outcomes if not o.answerable]
    judged = [o.judged for o in answerable if o.answered and o.judged is not None]
    regressions = [o for o in outcomes if o.is_regression]

    stages: dict[str, float] = {}
    for outcome in outcomes:
        for stage, cost in outcome.cost_by_stage.items():
            stages[stage] = stages.get(stage, 0.0) + cost
    latencies = [float(o.latency_ms) for o in outcomes if o.rejected_by is None]

    return AnswerMetrics(
        questions=len(outcomes),
        answered_rate=_share([o.answered for o in answerable]),
        refusal_rate=_share([not o.answered for o in out_of_domain]),
        citation_accuracy=_share([o.cites_expected for o in answerable]),
        context_recall=_share([bool(set(o.expected) & set(o.in_context)) for o in answerable]),
        faithfulness=_mean([j.faithfulness for j in judged]),
        relevance=_mean([j.relevance for j in judged]),
        correctness=_mean([o.judged.correctness if o.answered and o.judged is not None else 0.0 for o in answerable]),
        opening_consistency=_share([j.opening_holds for j in judged]),
        regressions_passed=sum(regression_passed(o) for o in regressions),
        regressions=len(regressions),
        cost_per_question_usd=_mean([o.service_cost for o in outcomes]),
        cost_by_stage_usd={stage: cost / len(outcomes) for stage, cost in sorted(stages.items())} if outcomes else {},
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
    )
