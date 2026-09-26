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

from app.domain.schemas.listing_agent_review import AgentFinding, TraceStep
from app.domain.schemas.listing_review import Listing
from app.foundation.llm.usage import LLMUsage
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_agent_critic_prompt
from app.foundation.text import appears_in
from app.generation.agentic.ports import RegulationFragment

log = structlog.get_logger()

# v2: `contradicts_listing` needs a quote of the listing, checked in code, after v1 rejected a
# correct deposit finding as contradicting a listing that said exactly that (ADR 0025).
PROMPT_VERSION = "v2"
# The whole article, never a cut: the critic reads only the cited fragments, and a rule cut off at
# the end of a long article (Catalan article 61 is 1,942 characters) is a rule it would reject for
# not being there. 6,000 is the longest a chunk can be (CHUNK_MAX_CHARS, ADR 0009).
SOURCE_CHARS = 6_000


class Problem(StrEnum):
    NONE = "none"
    CONTRADICTS_LISTING = "contradicts_listing"
    RULE_NOT_IN_SOURCES = "rule_not_in_sources"
    WRONG_ARTICLE = "wrong_article"


class FindingJudgement(BaseModel):
    finding_index: int = Field(description="El número de la incidencia")
    supported: bool = Field(description="True si el anuncio y los fragmentos la sostienen")
    problem: Problem = Field(description="Qué falla, o none")
    quote: str = Field(
        default="", description="Si el problema es contradicts_listing, la frase exacta del anuncio que lo demuestra"
    )
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
    stated = listing.as_text()
    supported, rejected = [], []
    for index, finding in enumerate(findings, start=1):
        judgement = by_index.get(index)
        if judgement is None or judgement.supported:
            supported.append(finding)
        elif judgement.problem == Problem.CONTRADICTS_LISTING and not appears_in(judgement.quote, stated):
            # The critic says the listing contradicts the finding but cannot show where: its word
            # alone does not remove a finding. Code checks the quote, as it checks the actor's.
            log.info("agent.critic_unverified_rejection", finding=finding.message[:80], quote=judgement.quote[:80])
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
            f"- Cita del anuncio: «{finding.evidence}»"
            if finding.evidence
            else "- Cita del anuncio: ninguna (dice que falta algo)",
        ]
        cited = [fragments[chunk_id] for chunk_id in finding.sources if chunk_id in fragments]
        if cited:
            lines.append("- Fragmentos que cita:")
            lines += [f"  [{f.chunk_id}] {f.law_title} · {f.article_title}\n  {f.text[:SOURCE_CHARS]}" for f in cited]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def feedback_for(rejected: list[Rejection]) -> str:
    """What the actor is told on a retry: each rejected finding, and why, in the critic's words."""
    lines = ["Un revisor ha comprobado tu revisión anterior y ha rechazado estas incidencias:"]
    lines += [f"- «{r.finding.message}» ({r.problem}): {r.reason}" for r in rejected]
    lines.append(
        "Vuelve a revisar el anuncio. No repitas esas incidencias salvo que puedas sostenerlas con el "
        "anuncio y con fragmentos que sí digan lo que afirmas."
    )
    return "\n".join(lines)


def critic_step(step: int, verdict: CriticResult) -> TraceStep:
    if verdict.unavailable:
        result = "El revisor no ha podido ejecutarse: se mantienen todas las incidencias."
    elif not verdict.rejected:
        result = "Todas las incidencias están respaldadas por el anuncio y la normativa."
    else:
        result = "; ".join(f"Rechazada «{r.finding.message[:80]}» ({r.problem})" for r in verdict.rejected)
    return TraceStep(step=step, tool="critic", result=result, ok=not verdict.rejected and not verdict.unavailable)


def boss_step(step: int, decision: str) -> TraceStep:
    return TraceStep(step=step, tool="boss", result=f"Decisión: {decision}")
