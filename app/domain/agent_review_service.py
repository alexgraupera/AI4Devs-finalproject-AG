"""The conductor of the agent review: where CAG, RAG and the agent meet.

The agent reads the regulatory checklist in its prompt (CAG), searches the BOE corpus through a
tool (RAG) and decides what to check and in which order (the agent). The pipeline of
`ListingReviewService` stays untouched next to it: both paths live, so they can be compared.

What this class adds around the loop is what must not be left to the model:

- The input guardrails and the spend cap, before any call.
- **Citations resolved from what the search returned.** The model names fragment numbers; the
  conductor builds the citation from the fragment. A number the search never returned is dropped.
- **No legal finding without a source.** A finding with a legal basis must cite a fragment the
  agent actually read, or be one of the checklist points whose article travels in the prompt.
  Anything else is a legal claim nobody can check, and it is dropped before the user sees it.
- **Actor, critic, boss** (ADR 0025). The critic, on the other provider, reads every finding against
  the listing and its sources; the boss (a function) accepts, sends the actor back once with the
  rejections quoted, or escalates to a person. A finding the critic rejects never reaches the user.
"""

import structlog

from app.domain.errors import NotAListing
from app.domain.schemas.listing_agent_review import (
    AgentFinding,
    AgentReview,
    AgentReviewedListing,
    CitedFinding,
    TraceStep,
)
from app.domain.schemas.listing_review import Listing, Severity, Verdict
from app.domain.schemas.regulation_answer import Citation
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import ALLOWED_LEGAL_BASIS
from app.foundation.guardrails.spend import SpendGuard
from app.foundation.llm.tools import ToolCallingLLM
from app.foundation.llm.usage import combined
from app.foundation.llm.wrapper import StructuredLLM
from app.generation.agentic.boss import (
    DEFAULT_ESCALATE_BELOW,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MIN_CONFIDENCE,
    BossDecision,
    decide,
)
from app.generation.agentic.critic import CriticResult, Rejection, criticise
from app.generation.agentic.loop import DEFAULT_MAX_ITERATIONS, DEFAULT_TIMEOUT_SECONDS, AgentLoop, AgentRun
from app.generation.agentic.ports import RegulationFragment, RegulationSearch
from app.generation.agentic.tools import CheckListingFields, SearchRegulations
from app.generation.rag.retriever import Retriever

log = structlog.get_logger()

# v2: decides the region before searching (v1 never searched the Catalan law for a Barcelona
# listing) and checks a datum is really absent before reporting it missing (ADR 0024).
PROMPT_VERSION = "v2"


class RetrieverSearch:
    """The concrete retriever behind the agent's port. The adapter lives here, in the conductor,
    so `agentic/` never imports `rag/`."""

    def __init__(self, retriever: Retriever, *, top_k: int, min_score: float | None = None) -> None:
        self._retriever = retriever
        self._top_k = top_k
        self._min_score = min_score

    async def search_regulations(
        self, query: str, *, jurisdictions: list[str] | None = None
    ) -> list[RegulationFragment]:
        chunks = await self._retriever.search(
            query, k=self._top_k, min_score=self._min_score, jurisdictions=jurisdictions
        )
        return [
            RegulationFragment(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                score=chunk.score,
                law_id=chunk.law_id,
                law_title=chunk.law_title,
                article_title=chunk.article_title,
                citation_url=chunk.citation_url,
                jurisdiction=chunk.jurisdiction,
            )
            for chunk in chunks
        ]


class AgentReviewService:
    def __init__(
        self,
        llm: ToolCallingLLM,
        search: RegulationSearch,
        moderation: ModerationClient | None = None,
        *,
        model: str = "",
        prompt_version: str = PROMPT_VERSION,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_fragments: int = 5,
        spend: SpendGuard | None = None,
        critic: StructuredLLM | None = None,
        critic_min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        critic_escalate_below: float = DEFAULT_ESCALATE_BELOW,
        max_review_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._llm = llm
        self._search = search
        self._moderation = moderation
        self._model = model
        self._prompt_version = prompt_version
        self._max_iterations = max_iterations
        self._timeout = timeout_seconds
        self._max_fragments = max_fragments
        self._spend = spend
        self._critic = critic
        self._critic_min_confidence = critic_min_confidence
        self._critic_escalate_below = critic_escalate_below
        self._max_review_attempts = max_review_attempts

    async def review(self, listing: Listing) -> AgentReviewedListing:
        await check_input(listing.text, moderation=self._moderation)
        if self._spend is not None:
            await self._spend.check()

        loop = AgentLoop(
            self._llm,
            [CheckListingFields(listing), SearchRegulations(self._search, max_fragments=self._max_fragments)],
            max_iterations=self._max_iterations,
            timeout_seconds=self._timeout,
            prompt_version=self._prompt_version,
        )
        run = await loop.run(listing)
        trace, usage = list(run.trace), run.usage

        if not run.output.is_rental_listing:
            # Nothing to criticise in a review of something that is not a listing.
            if self._spend is not None:
                await self._spend.record(usage.estimated_cost_usd)
            raise NotAListing(run.output.summary)

        findings, escalated, dropped = run.output.findings, False, 0
        if self._critic is not None:
            attempt = 1
            while True:
                verdict = await criticise(run.output.findings, listing, run.fragments, self._critic)
                usage = combined(usage, verdict.usage)
                decision = decide(
                    verdict,
                    attempt=attempt,
                    max_attempts=self._max_review_attempts,
                    min_confidence=self._critic_min_confidence,
                    escalate_below=self._critic_escalate_below,
                )
                trace += [_critic_step(len(trace) + 1, verdict), _boss_step(len(trace) + 2, decision)]
                log.info(
                    "agent_review.critic",
                    attempt=attempt,
                    confidence=verdict.confidence,
                    rejected=[r.problem for r in verdict.rejected],
                    unavailable=verdict.unavailable,
                    decision=decision,
                )
                if decision != BossDecision.RETRY:
                    findings, escalated, dropped = (
                        verdict.supported,
                        decision == BossDecision.ESCALATE,
                        len(verdict.rejected),
                    )
                    break
                attempt += 1
                run = await loop.run(listing, feedback=_feedback(verdict.rejected))
                trace += [step.model_copy(update={"step": len(trace) + i}) for i, step in enumerate(run.trace, start=1)]
                usage = combined(usage, run.usage)

        if self._spend is not None:
            await self._spend.record(usage.estimated_cost_usd)

        log.info(
            "agent_review.completed",
            prompt_version=self._prompt_version,
            model=usage.model,
            stop_reason=run.stop_reason,
            steps=len(trace),
            tools_called=[step.tool for step in trace],
            fragments_read=len(run.fragments),
            escalated=escalated,
            dropped_findings=dropped,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
            estimated_cost_usd=float(usage.estimated_cost_usd) if usage.estimated_cost_usd is not None else None,
        )
        return AgentReviewedListing(
            review=self._checked(findings, run),
            trace=trace,
            usage=usage,
            stop_reason=run.stop_reason,
            escalated=escalated,
            dropped_findings=dropped,
        )

    def _checked(self, findings: list[AgentFinding], run: AgentRun) -> AgentReview:
        cited = [self._cited(finding, run.fragments) for finding in findings]
        kept = [finding for finding in cited if finding is not None]
        verdict = Verdict.REQUEST_CHANGES if any(f.severity == Severity.HIGH for f in kept) else Verdict.APPROVE
        if len(kept) != len(run.output.findings) or verdict != run.output.verdict:
            log.info("agent_review.verdict_recomputed", model_verdict=run.output.verdict, verdict=verdict)
        return AgentReview(findings=kept, verdict=verdict, summary=run.output.summary)

    def _cited(self, finding: AgentFinding, fragments: dict[int, RegulationFragment]) -> CitedFinding | None:
        citations = []
        for chunk_id in dict.fromkeys(finding.sources):
            fragment = fragments.get(chunk_id)
            if fragment is None:
                log.warning("agent_review.invented_source", chunk_id=chunk_id, model=self._model)
                continue
            citations.append(
                Citation(
                    law_id=fragment.law_id,
                    law_title=fragment.law_title,
                    article=fragment.article_title,
                    url=fragment.citation_url,
                    chunk_id=fragment.chunk_id,
                )
            )

        if finding.legal_basis and not citations and finding.legal_basis not in ALLOWED_LEGAL_BASIS:
            # A legal claim with no fragment behind it and outside the checklist: nobody can check it.
            log.warning("guardrail.dropped_finding", reason="unsourced", legal_basis=finding.legal_basis)
            return None

        return CitedFinding(
            category=finding.category,
            severity=finding.severity,
            message=finding.message,
            suggestion=finding.suggestion,
            legal_basis=finding.legal_basis,
            citations=citations,
        )


def _feedback(rejected: list[Rejection]) -> str:
    """What the actor is told on a retry: each rejected finding, and why, in the critic's words."""
    lines = ["Un revisor ha comprobado tu revisión anterior y ha rechazado estas incidencias:"]
    lines += [f"- «{r.finding.message}» ({r.problem}): {r.reason}" for r in rejected]
    lines.append(
        "Vuelve a revisar el anuncio. No repitas esas incidencias salvo que puedas sostenerlas con el "
        "anuncio y con fragmentos que sí digan lo que afirmas."
    )
    return "\n".join(lines)


def _critic_step(step: int, verdict: CriticResult) -> TraceStep:
    if verdict.unavailable:
        result = "El revisor no ha podido ejecutarse: se mantienen todas las incidencias."
    elif not verdict.rejected:
        result = "Todas las incidencias están respaldadas por el anuncio y la normativa."
    else:
        result = "; ".join(f"Rechazada «{r.finding.message[:80]}» ({r.problem})" for r in verdict.rejected)
    return TraceStep(step=step, tool="critic", result=result, ok=not verdict.rejected and not verdict.unavailable)


def _boss_step(step: int, decision: BossDecision) -> TraceStep:
    return TraceStep(step=step, tool="boss", result=f"Decisión: {decision}")
