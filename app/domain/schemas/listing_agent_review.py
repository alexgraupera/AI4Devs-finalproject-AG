"""The contract of the agent review: what the model submits, and what the caller receives.

The agent reuses the review vocabulary of the pipeline (`Finding`, `Verdict`) and the citation of
the regulation Q&A (`Citation`), so the two paths can be compared field by field. What it adds is
where each legal finding came from: the model names the numbers of the fragments it read, and the
conductor turns those numbers into citations from what the search tool actually returned.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.schemas.listing_review import Finding, Verdict
from app.domain.schemas.regulation_answer import Citation
from app.foundation.llm.usage import LLMUsage


class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"


class AgentFinding(Finding):
    evidence: str = Field(
        default="",
        description=(
            "La frase exacta del anuncio (o el dato estructurado) a la que se refiere la incidencia, "
            "copiada literalmente. Vacío si la incidencia es que falta algo"
        ),
    )
    sources: list[int] = Field(
        default_factory=list,
        description=(
            "Números de los fragmentos de normativa que sostienen la incidencia, tal como aparecieron "
            "en search_regulations. Vacío si la incidencia no es legal"
        ),
    )


class AgentReviewCandidate(BaseModel):
    """What the model submits through `submit_review`. The decision about the text comes first."""

    is_rental_listing: bool = Field(description="False si el texto no es un anuncio de alquiler de vivienda")
    findings: list[AgentFinding]
    verdict: Verdict = Field(description="request_changes si hay alguna incidencia de severidad high")
    summary: str = Field(description="Una o dos frases en español que resumen la revisión")


class CitedFinding(Finding):
    citations: list[Citation] = Field(default_factory=list)


class ListingRewrite(BaseModel):
    """The listing corrected for its findings, for the person publishing to accept or edit."""

    text: str
    changes: list[str]
    # Data the listing must give and the agent may not invent, left as gaps in square brackets.
    placeholders: list[str] = Field(default_factory=list)
    # Figures in the rewrite that the original does not state: to check before publishing.
    new_figures: list[str] = Field(default_factory=list)


class AgentReview(BaseModel):
    findings: list[CitedFinding]
    verdict: Verdict
    summary: str
    rewrite: ListingRewrite | None = None


class HumanAction(StrEnum):
    APPROVE = "approve"
    ADJUST = "adjust"
    REJECT = "reject"


class HumanDecision(BaseModel):
    """What a person decides on a paused review."""

    action: HumanAction
    # For `adjust`: the positions (from 0) of the proposed findings that stand. The rest are dropped.
    keep: list[int] | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _adjust_says_what_stays(self) -> "HumanDecision":
        if self.action == HumanAction.ADJUST and self.keep is None:
            raise ValueError("adjust needs `keep`: the findings that stand")
        return self


class RejectedFinding(BaseModel):
    """A finding the critic did not back, shown to the person so they can see why."""

    message: str
    legal_basis: str | None
    problem: str
    reason: str


class TraceStep(BaseModel):
    """One step of a run, for debugging and for the person reading the review."""

    step: int
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    ok: bool = True
    latency_ms: int = 0
    # What the model wrote alongside its tool calls, when it wrote anything: its reasoning.
    thought: str | None = None


class HumanReviewRequest(BaseModel):
    """A review the agent could not stand behind, waiting for a person before it is published."""

    run_id: str
    reason: str
    proposed: AgentReview
    rejected: list[RejectedFinding] = Field(default_factory=list)


class Step(StrEnum):
    """Where a review spends: the actor's turns, the tools it runs, the critic, the rewrite."""

    PLAN = "plan"
    TOOLS = "tools"
    CRITIC = "critic"
    REWRITE = "rewrite"


@dataclass(frozen=True)
class StepCost:
    step: str
    # Model calls billed, retries included; tool executions for `tools`.
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: Decimal | None

    def __add__(self, other: "StepCost") -> "StepCost":
        costs = [c for c in (self.estimated_cost_usd, other.estimated_cost_usd) if c is not None]
        return StepCost(
            step=self.step,
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
            estimated_cost_usd=sum(costs, Decimal(0)) if costs else None,
        )


@dataclass(frozen=True)
class CostBreakdown:
    """A review's cost step by step, so the next optimisation is read rather than argued (#52).

    Tools cost no tokens: their step carries their calls and their time. The embedding of a search
    query is not priced (a query is ~20 tokens; at $0.13 per million it is below the rounding).
    """

    steps: list[StepCost] = field(default_factory=list)

    @classmethod
    def of(cls, calls: Sequence[tuple[Step, LLMUsage]], tool_steps: Sequence["TraceStep"] = ()) -> "CostBreakdown":
        breakdown = cls()
        for step, usage in calls:
            breakdown = breakdown.add(step, usage)
        if tool_steps:
            breakdown = breakdown._merged(
                StepCost(
                    step=Step.TOOLS,
                    calls=len(tool_steps),
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=sum(s.latency_ms for s in tool_steps),
                    estimated_cost_usd=Decimal(0),
                )
            )
        return breakdown

    def add(self, step: Step, usage: LLMUsage | None) -> "CostBreakdown":
        if usage is None:
            return self
        return self._merged(
            StepCost(
                step=step,
                calls=usage.attempts,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=usage.latency_ms,
                estimated_cost_usd=usage.estimated_cost_usd,
            )
        )

    @property
    def total(self) -> StepCost:
        total = StepCost("total", 0, 0, 0, 0, None)
        for step in self.steps:
            total = total + step
        return total

    def _merged(self, cost: StepCost) -> "CostBreakdown":
        by_step = {s.step: s for s in self.steps}
        by_step[cost.step] = by_step[cost.step] + cost if cost.step in by_step else cost
        order = list(Step)
        return CostBreakdown(sorted(by_step.values(), key=lambda s: order.index(Step(s.step))))


@dataclass(frozen=True)
class AgentReviewedListing:
    review: AgentReview
    trace: list[TraceStep]
    usage: LLMUsage
    stop_reason: StopReason
    # The critic could not back every conclusion even after a retry: a person has to look.
    escalated: bool = False
    # How many findings the critic removed because the listing or the sources did not hold them.
    dropped_findings: int = 0
    # The graph's thread id when the review ran as a graph (#41): the handle a pause is resumed by.
    run_id: str | None = None
    # Set exactly when the run is paused, waiting for a person (#42).
    pending_review: HumanReviewRequest | None = None
    # What the person decided, once they have.
    human_decision: HumanDecision | None = None
    # Where the cost went, step by step (#52).
    cost: CostBreakdown = field(default_factory=CostBreakdown)
