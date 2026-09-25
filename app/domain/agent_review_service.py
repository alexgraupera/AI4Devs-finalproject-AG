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
"""

import structlog

from app.domain.errors import NotAListing
from app.domain.schemas.listing_agent_review import (
    AgentFinding,
    AgentReview,
    AgentReviewedListing,
    CitedFinding,
)
from app.domain.schemas.listing_review import Listing, Severity, Verdict
from app.domain.schemas.regulation_answer import Citation
from app.foundation.guardrails.input import ModerationClient, check_input
from app.foundation.guardrails.output import ALLOWED_LEGAL_BASIS
from app.foundation.guardrails.spend import SpendGuard
from app.foundation.llm.tools import ToolCallingLLM
from app.generation.agentic.loop import DEFAULT_MAX_ITERATIONS, DEFAULT_TIMEOUT_SECONDS, AgentLoop, AgentRun
from app.generation.agentic.ports import RegulationFragment, RegulationSearch
from app.generation.agentic.tools import CheckListingFields, SearchRegulations
from app.generation.rag.retriever import Retriever

log = structlog.get_logger()

PROMPT_VERSION = "v1"


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
        if self._spend is not None:
            await self._spend.record(run.usage.estimated_cost_usd)

        log.info(
            "agent_review.completed",
            prompt_version=self._prompt_version,
            model=run.usage.model,
            stop_reason=run.stop_reason,
            steps=len(run.trace),
            tools_called=[step.tool for step in run.trace],
            fragments_read=len(run.fragments),
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            latency_ms=run.usage.latency_ms,
            estimated_cost_usd=float(run.usage.estimated_cost_usd)
            if run.usage.estimated_cost_usd is not None
            else None,
        )

        if not run.output.is_rental_listing:
            raise NotAListing(run.output.summary)

        return AgentReviewedListing(
            review=self._checked(run), trace=run.trace, usage=run.usage, stop_reason=run.stop_reason
        )

    def _checked(self, run: AgentRun) -> AgentReview:
        findings = [self._cited(finding, run.fragments) for finding in run.output.findings]
        kept = [finding for finding in findings if finding is not None]
        verdict = Verdict.REQUEST_CHANGES if any(f.severity == Severity.HIGH for f in kept) else Verdict.APPROVE
        if len(kept) != len(findings) or verdict != run.output.verdict:
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
