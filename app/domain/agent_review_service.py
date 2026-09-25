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

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from app.domain.errors import NotAListing
from app.domain.graph.listing_review_graph import GraphConfig, build_review_graph, critic_from_json
from app.domain.graph.state import ReviewState, fragments_from_json, usage_from_json
from app.domain.schemas.listing_agent_review import (
    AgentFinding,
    AgentReview,
    AgentReviewCandidate,
    AgentReviewedListing,
    CitedFinding,
    StopReason,
    TraceStep,
)
from app.domain.schemas.listing_review import Listing, Severity, Verdict
from app.domain.schemas.regulation_answer import Citation
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import ALLOWED_LEGAL_BASIS
from app.foundation.guardrails.spend import SpendGuard
from app.foundation.llm.tools import ToolCallingLLM
from app.foundation.llm.usage import LLMUsage, combined
from app.foundation.llm.wrapper import StructuredLLM
from app.foundation.prompts.loader import render_agent_review_prompt
from app.foundation.text import appears_in
from app.generation.agentic.boss import (
    DEFAULT_ESCALATE_BELOW,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MIN_CONFIDENCE,
    BossDecision,
    decide,
)
from app.generation.agentic.critic import boss_step, critic_step, criticise, feedback_for
from app.generation.agentic.loop import DEFAULT_MAX_ITERATIONS, DEFAULT_TIMEOUT_SECONDS, AgentLoop
from app.generation.agentic.ports import RegulationFragment, RegulationSearch
from app.generation.agentic.tools import CheckListingFields, SearchRegulations
from app.generation.rag.retriever import Retriever

log = structlog.get_logger()

# v2: decides the region before searching (v1 never searched the Catalan law for a Barcelona
# listing) and checks a datum is really absent before reporting it missing (ADR 0024).
# v3: quotes the listing in `evidence` for every finding about what it says (ADR 0025).
PROMPT_VERSION = "v3"


Checkpoints = Callable[[], Awaitable[BaseCheckpointSaver[Any]]]


@dataclass(frozen=True)
class _Run:
    """What either orchestrator hands back: the rest of the review does not care which one ran."""

    orchestrator: str
    candidate: AgentReviewCandidate
    findings: list[AgentFinding]
    fragments: dict[int, RegulationFragment]
    trace: list[TraceStep]
    usage: LLMUsage
    stop_reason: StopReason
    escalated: bool = False
    dropped: int = 0
    run_id: str | None = None


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
        checkpoints: Checkpoints | None = None,
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
        # With a checkpoint store the review runs as a graph; without one, as the hand-written loop.
        self._checkpoints = checkpoints
        self._graph: CompiledStateGraph[Any, Any, Any, Any] | None = None
        self._graph_config = GraphConfig(
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds,
            max_attempts=max_review_attempts,
            min_confidence=critic_min_confidence,
            escalate_below=critic_escalate_below,
            max_fragments=max_fragments,
        )

    async def review(self, listing: Listing) -> AgentReviewedListing:
        await check_input(listing.text, moderation=self._moderation)
        if self._spend is not None:
            await self._spend.check()

        run = await (self._run_graph(listing) if self._checkpoints is not None else self._run_loop(listing))
        if self._spend is not None:
            await self._spend.record(run.usage.estimated_cost_usd)

        if not run.candidate.is_rental_listing:
            raise NotAListing(run.candidate.summary)

        log.info(
            "agent_review.completed",
            orchestrator=run.orchestrator,
            run_id=run.run_id,
            prompt_version=self._prompt_version,
            model=run.usage.model,
            stop_reason=run.stop_reason,
            steps=len(run.trace),
            tools_called=[step.tool for step in run.trace],
            fragments_read=len(run.fragments),
            escalated=run.escalated,
            dropped_findings=run.dropped,
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            latency_ms=run.usage.latency_ms,
            estimated_cost_usd=float(run.usage.estimated_cost_usd)
            if run.usage.estimated_cost_usd is not None
            else None,
        )
        return AgentReviewedListing(
            review=self._checked(run.findings, run.candidate, run.fragments, listing),
            trace=run.trace,
            usage=run.usage,
            stop_reason=run.stop_reason,
            escalated=run.escalated,
            dropped_findings=run.dropped,
            run_id=run.run_id,
        )

    async def _run_loop(self, listing: Listing) -> _Run:
        """The hand-written orchestration (#38, #40), kept as the reference the graph is measured against."""
        loop = AgentLoop(
            self._llm,
            [CheckListingFields(listing), SearchRegulations(self._search, max_fragments=self._max_fragments)],
            max_iterations=self._max_iterations,
            timeout_seconds=self._timeout,
            prompt_version=self._prompt_version,
        )
        run = await loop.run(listing)
        trace, usage = list(run.trace), run.usage
        findings, escalated, dropped = run.output.findings, False, 0

        if self._critic is not None and run.output.is_rental_listing:
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
                trace += [critic_step(len(trace) + 1, verdict), boss_step(len(trace) + 2, decision)]
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
                run = await loop.run(listing, feedback=feedback_for(verdict.rejected))
                trace += [step.model_copy(update={"step": len(trace) + i}) for i, step in enumerate(run.trace, start=1)]
                usage = combined(usage, run.usage)

        return _Run(
            orchestrator="loop",
            candidate=run.output,
            findings=findings,
            fragments=run.fragments,
            trace=trace,
            usage=usage,
            stop_reason=run.stop_reason,
            escalated=escalated,
            dropped=dropped,
        )

    async def _run_graph(self, listing: Listing) -> _Run:
        """The same flow as a LangGraph graph, its state checkpointed after every node (#41)."""
        assert self._checkpoints is not None
        checkpointer = await self._checkpoints()
        if self._graph is None:
            self._graph = build_review_graph(
                llm=self._llm,
                search=self._search,
                critic=self._critic,
                config=self._graph_config,
                checkpointer=checkpointer,
            )

        run_id = str(uuid4())
        system, user = render_agent_review_prompt(listing, version=self._prompt_version)
        initial: ReviewState = {
            "listing": listing.model_dump(mode="json"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "trace": [],
            "usage": [],
            "fragments": {},
            "failures": {},
            "iterations": 0,
            "attempt": 1,
            "deadline": time.time() + self._timeout,
        }
        config: RunnableConfig = {
            "configurable": {"thread_id": run_id},
            "recursion_limit": self._graph_config.recursion_limit,
        }
        try:
            final = await self._graph.ainvoke(initial, config)
        finally:
            # Retention: a finished run leaves nothing behind. The checkpoint holds the listing's
            # text, and the service keeps no listings (ADR 0018); the trace goes back in the response.
            await checkpointer.adelete_thread(run_id)

        usages = [usage_from_json(u) for u in final.get("usage", [])]
        usage = usages[0]
        for more in usages[1:]:
            usage = combined(usage, more)
        critic = critic_from_json(final["critic"]) if final.get("critic") else None
        candidate = AgentReviewCandidate.model_validate(final["candidate"])
        return _Run(
            orchestrator="graph",
            run_id=run_id,
            candidate=candidate,
            findings=critic.supported if critic is not None else candidate.findings,
            fragments=fragments_from_json(final.get("fragments", {})),
            trace=[TraceStep.model_validate(step) for step in final.get("trace", [])],
            usage=usage,
            stop_reason=StopReason(final.get("stop_reason") or StopReason.COMPLETED),
            escalated=final.get("outcome") == BossDecision.ESCALATE.value,
            dropped=len(critic.rejected) if critic is not None else 0,
        )

    def _checked(
        self,
        findings: list[AgentFinding],
        candidate: AgentReviewCandidate,
        fragments: dict[int, RegulationFragment],
        listing: Listing,
    ) -> AgentReview:
        stated = listing.as_text()
        cited = [self._cited(finding, fragments) for finding in findings if _quotes_the_listing(finding, stated)]
        kept = [finding for finding in cited if finding is not None]
        verdict = Verdict.REQUEST_CHANGES if any(f.severity == Severity.HIGH for f in kept) else Verdict.APPROVE
        if len(kept) != len(candidate.findings) or verdict != candidate.verdict:
            log.info("agent_review.verdict_recomputed", model_verdict=candidate.verdict, verdict=verdict)
        return AgentReview(findings=kept, verdict=verdict, summary=candidate.summary)

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


def _quotes_the_listing(finding: AgentFinding, stated: str) -> bool:
    """A finding about what the listing says must quote it, and the quote must be there.

    A finding that invents its own evidence ("honorarios a cargo del inquilino" in a listing that
    says the opposite) is dropped here, in code, before any model is asked about it. A finding
    about what is missing quotes nothing, and passes.
    """
    if not finding.evidence or appears_in(finding.evidence, stated):
        return True
    log.warning("guardrail.dropped_finding", reason="evidence_not_in_listing", evidence=finding.evidence[:120])
    return False
