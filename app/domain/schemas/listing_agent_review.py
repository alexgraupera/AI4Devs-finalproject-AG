"""The contract of the agent review: what the model submits, and what the caller receives.

The agent reuses the review vocabulary of the pipeline (`Finding`, `Verdict`) and the citation of
the regulation Q&A (`Citation`), so the two paths can be compared field by field. What it adds is
where each legal finding came from: the model names the numbers of the fragments it read, and the
conductor turns those numbers into citations from what the search tool actually returned.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.schemas.listing_review import Finding, Verdict
from app.domain.schemas.regulation_answer import Citation
from app.foundation.llm.usage import LLMUsage


class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"


class AgentFinding(Finding):
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


class AgentReview(BaseModel):
    findings: list[CitedFinding]
    verdict: Verdict
    summary: str


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
