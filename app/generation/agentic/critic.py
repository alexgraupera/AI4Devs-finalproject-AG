"""The critic: reads each finding against the listing and the fragments it cites, and says whether they hold.

The actor's loop proves structure (a legal finding cites a fragment the agent read). It cannot
prove meaning: that the cited article says what the finding claims, or that the listing lacks what
the finding says it lacks. The first hand check of #38 produced exactly that second failure: a
rating reported missing that the listing stated. Only reading both catches it.

The critic never rewrites a finding and never adds one: it judges, per finding, with a typed problem
(the session on actor-critic-boss asks for typed feedback, not a mood). It runs on the judge's model,
the other provider from the actor's, so it does not share the actor's blind spots (ADR 0023).

A critic that cannot run is not evidence that the findings are wrong: it fails open, and says so.
"""

from dataclasses import dataclass, field
from enum import StrEnum

import structlog
from pydantic import BaseModel, Field

from app.domain.schemas.listing_agent_review import AgentFinding
from app.domain.schemas.listing_review import Listing
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_agent_critic_prompt
from app.generation.agentic.ports import RegulationFragment

log = structlog.get_logger()

PROMPT_VERSION = "v1"
SOURCE_CHARS = 1_500


class Problem(StrEnum):
    NONE = "none"
    CONTRADICTS_LISTING = "contradicts_listing"
    RULE_NOT_IN_SOURCES = "rule_not_in_sources"
    WRONG_ARTICLE = "wrong_article"


class FindingJudgement(BaseModel):
    finding_index: int = Field(description="El número de la incidencia")
    supported: bool = Field(description="True si el anuncio y los fragmentos la sostienen")
    problem: Problem = Field(description="Qué falla, o none")
    reason: str = Field(description="Una frase: qué dice la incidencia y qué dicen el anuncio o los fragmentos")


class CriticVerdict(BaseModel):
    judgements: list[FindingJudgement] = Field(description="Una por incidencia")


@dataclass(frozen=True)
class Rejection:
    finding: AgentFinding
    problem: Problem
    reason: str


@dataclass(frozen=True)
class CriticResult:
    supported: list[AgentFinding]
    rejected: list[Rejection] = field(default_factory=list)
    # Share of the findings the critic supports. 1.0 with no findings: nothing to doubt.
    confidence: float = 1.0
    usage: LLMUsage | None = None
    # The critic could not run, so nothing was judged and everything was kept.
    unavailable: bool = False


async def criticise(
    findings: list[AgentFinding],
    listing: Listing,
    fragments: dict[int, RegulationFragment],
    llm: StructuredLLM,
    *,
    prompt_version: str = PROMPT_VERSION,
) -> CriticResult:
    if not findings:
        return CriticResult(supported=[])

    system, user = render_agent_critic_prompt(listing, _render(findings, fragments), version=prompt_version)
    try:
        completion = await llm.complete_structured(system=system, user=user, schema=CriticVerdict)
    except Exception:
        log.warning("agent.critic_unavailable", exc_info=True)
        return CriticResult(supported=list(findings), unavailable=True)

    # A judgement for a finding that does not exist is ignored; a finding the critic did not
    # judge is kept: the critic did not object to it.
    by_index = {j.finding_index: j for j in completion.output.judgements if 1 <= j.finding_index <= len(findings)}
    supported, rejected = [], []
    for index, finding in enumerate(findings, start=1):
        judgement = by_index.get(index)
        if judgement is None or judgement.supported:
            supported.append(finding)
        else:
            rejected.append(Rejection(finding=finding, problem=judgement.problem, reason=judgement.reason))

    return CriticResult(
        supported=supported,
        rejected=rejected,
        confidence=len(supported) / len(findings),
        usage=completion.usage,
    )


def _render(findings: list[AgentFinding], fragments: dict[int, RegulationFragment]) -> str:
    blocks = []
    for index, finding in enumerate(findings, start=1):
        lines = [
            f"## Incidencia {index}",
            f"- Mensaje: {finding.message}",
            f"- Base legal: {finding.legal_basis or 'ninguna (incidencia de calidad)'}",
            f"- Gravedad: {finding.severity}",
        ]
        cited = [fragments[chunk_id] for chunk_id in finding.sources if chunk_id in fragments]
        if cited:
            lines.append("- Fragmentos que cita:")
            lines += [f"  [{f.chunk_id}] {f.law_title} · {f.article_title}\n  {f.text[:SOURCE_CHARS]}" for f in cited]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
