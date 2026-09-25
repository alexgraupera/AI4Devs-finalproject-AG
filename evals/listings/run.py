"""`make eval-listings`: review the annotated listings with the pipeline, the agent, or both.

Each listing goes through the real service as a request would (guardrails included, cache and spend
cap bypassed), and the legal findings are scored against the annotation. The same listings through
both paths is the comparison of #52: what the agent's extra calls buy.

    python -m evals.listings.run --path cag      # the pipeline of #1, one model call per review
    python -m evals.listings.run --path cag --cag-prompt v3   # a prompt version against the current one
    python -m evals.listings.run --path agent    # the agent of #3, with its critic
    python -m evals.listings.run                 # both
    python -m evals.listings.run --path agent --only barcelona-offer-incomplete   # one case, cents
    python -m evals.listings.run --path agent --repeat 3 --only a,b,c             # the variance of a few cases

The agent runs as the graph with an in-memory checkpointer and the human pause off: an escalation
is recorded, not waited on. The rewrite is off too: it is not what is scored, and it costs a call.
"""

import argparse
import asyncio
import json
import logging
import pathlib
import re
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol

from app.config import get_settings
from app.domain.agent_review_service import TOOL_NAMES, AgentReviewService, RetrieverSearch
from app.domain.errors import NotAListing
from app.domain.legal_refs import LegalRef, citation_ref, legal_ref
from app.domain.listing_review_service import PROMPT_VERSION, ListingReviewService
from app.domain.schemas.listing_agent_review import AgentReviewedListing, TraceStep
from app.domain.schemas.listing_review import Listing, ReviewedListing
from app.foundation.guardrails.input import InputGuardrailViolation, ModerationClient
from app.foundation.guardrails.moderation import LiteLLMModeration
from app.foundation.guardrails.output import check_review
from app.foundation.persistence.checkpoints import MemoryCheckpoints
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.agentic.tools import SearchRegulations
from app.generation.rag.embeddings import LiteLLMEmbeddings
from app.generation.rag.retriever import Retriever
from evals.answers.run import wrapper_for
from evals.listings.dataset import AnnotatedListing, load_listings
from evals.listings.metrics import Failure, ListingMetrics, ListingOutcome, failure_counts, summarise

RESULTS_DIR = pathlib.Path(__file__).parents[1] / "results"
PATHS = ("cag", "agent")


class PipelineReviews(Protocol):
    async def review(self, listing: Listing) -> ReviewedListing: ...


class AgentReviews(Protocol):
    async def review(self, listing: Listing) -> AgentReviewedListing: ...


class _DroppedFindings(logging.Handler):
    """Counts the findings the output guardrail drops: it logs each one, and the review does not say."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == "guardrail.dropped_finding":
            self.count += 1


async def review_with_pipeline(case: AnnotatedListing, service: PipelineReviews) -> ListingOutcome:
    outcome = _outcome(case)
    guardrail = logging.getLogger(check_review.__module__)
    dropped = _DroppedFindings()
    guardrail.addHandler(dropped)
    started = time.perf_counter()
    try:
        reviewed = await service.review(case.listing)
    except Exception as error:
        outcome.error = _refusal(error)
        return outcome
    finally:
        guardrail.removeHandler(dropped)
    outcome.dropped = dropped.count
    outcome.latency_ms = int((time.perf_counter() - started) * 1000)
    for finding in reviewed.review.findings:
        if (ref := legal_ref(finding.legal_basis)) is not None:
            outcome.found.add(ref)
            outcome.notes.append((ref, finding.message))
    outcome.verdict = reviewed.review.verdict.value
    outcome.cost_usd = float(reviewed.usage.estimated_cost_usd or 0)
    outcome.step_costs = {"review": outcome.cost_usd}
    return outcome


async def review_with_agent(case: AnnotatedListing, service: AgentReviews) -> ListingOutcome:
    outcome = _outcome(case)
    started = time.perf_counter()
    try:
        reviewed = await service.review(case.listing)
    except Exception as error:
        outcome.error = _refusal(error)
        return outcome
    outcome.latency_ms = int((time.perf_counter() - started) * 1000)
    for finding in reviewed.review.findings:
        # A finding may name its article only through its citations.
        refs = [legal_ref(finding.legal_basis), *(citation_ref(c.law_id, c.article) for c in finding.citations)]
        ref = next((r for r in refs if r is not None), None)
        if ref is not None:
            outcome.found.add(ref)
            outcome.notes.append((ref, finding.message))
    outcome.verdict = reviewed.review.verdict.value
    outcome.escalated = reviewed.escalated
    outcome.dropped = reviewed.dropped_findings
    outcome.trace = [
        {"tool": step.tool, "arguments": step.arguments, "ok": step.ok, "result": step.result[:600]}
        for step in reviewed.trace
    ]
    outcome.cost_usd = float(reviewed.usage.estimated_cost_usd or 0)
    outcome.stop_reason = reviewed.stop_reason.value
    outcome.read = articles_read(reviewed.trace)
    outcome.rejected = critic_rejections(reviewed.trace)
    outcome.tool_errors = sum(1 for step in reviewed.trace if step.tool in TOOL_NAMES and not step.ok)
    outcome.step_costs = {step.step: float(step.estimated_cost_usd or 0) for step in reviewed.cost.steps}
    return outcome


# "[245] Ley 18/2007, de 28 de diciembre, ... · Artículo 61 (normativa de Cataluña)", as the search tool writes it.
_FRAGMENT = re.compile(r"^\[\d+\] (.+?) · (Art[íi]culo \d+)", re.MULTILINE)
# "Rechazada «...» [Ley 18/2007 art. 61.2] (rule_not_in_sources)", as the critic's step writes it.
_REJECTION = re.compile(r"\[([^\]]+)\] \((\w+)\)")


def articles_read(trace: list[TraceStep]) -> set[LegalRef]:
    """Every article a search returned to the agent: what it could have cited."""
    read = set()
    for step in trace:
        if step.tool == SearchRegulations.spec.name and step.ok:
            for law, article in _FRAGMENT.findall(step.result):
                if (ref := legal_ref(f"{article} de {law}")) is not None:
                    read.add(ref)
    return read


def critic_rejections(trace: list[TraceStep]) -> list[tuple[LegalRef | None, str]]:
    """Every finding the critic rejected, as its article and the problem the critic named."""
    return [
        (legal_ref(basis), problem)
        for step in trace
        if step.tool == "critic"
        for basis, problem in _REJECTION.findall(step.result)
    ]


def _refusal(error: Exception) -> str:
    """What a failed review is recorded as: the refusal's reason, or the error's type."""
    if isinstance(error, InputGuardrailViolation):
        return str(error.reason)
    if isinstance(error, NotAListing):
        return "not_a_listing"
    return type(error).__name__


def _outcome(case: AnnotatedListing) -> ListingOutcome:
    return ListingOutcome(
        id=case.id,
        tags=case.tags,
        expected=set(case.expected_legal),
        expected_verdict=case.expected_verdict,
        expected_error=case.expected_error,
    )


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def render(results: dict[str, tuple[ListingMetrics, list[ListingOutcome]]]) -> str:
    lines = [
        "| Path | precision | recall | F1 | clean false positives | verdict | adversarial handled "
        "| escalated | dropped | failures | cost / review | p50 | p95 |",
        "|---|" + "---:|" * 12,
    ]
    for path, (m, _) in results.items():
        lines.append(
            f"| `{path}` | {m.precision:.0%} | {m.recall:.0%} | {m.f1:.2f} | {_percent(m.clean_false_positive_rate)} "
            f"| {m.verdict_accuracy:.0%} | {_percent(m.adversarial_handled)} | {m.escalation_rate:.0%} "
            f"| {m.dropped_findings} | {m.failures} "
            f"| ${m.cost_per_review_usd:.4f} | {m.p50_latency_ms / 1000:.1f} s | {m.p95_latency_ms / 1000:.1f} s |"
        )
    for path, (_, outcomes) in results.items():
        repeats = max((o.repeat for o in outcomes), default=1)
        if repeats > 1:
            by_repeat = [summarise([o for o in outcomes if o.repeat == r]) for r in range(1, repeats + 1)]
            lines += ["", f"`{path}` by repeat: F1 " + ", ".join(f"{m.f1:.2f}" for m in by_repeat)]
    lines += _failures(results) + _step_costs(results)
    for path, (_, outcomes) in results.items():
        lines += _by_listing(path, outcomes)
    return "\n".join(lines)


def _failures(results: dict[str, tuple[ListingMetrics, list[ListingOutcome]]]) -> list[str]:
    counts = {path: failure_counts(outs, traced=path.startswith("agent")) for path, (_, outs) in results.items()}
    kinds = [kind for kind in Failure if any(kind in c for c in counts.values())]
    if not kinds:
        return []
    lines = ["", "**Failures, by the step that lost them**", "", "| Failure | " + " | ".join(counts) + " |"]
    lines.append("|---|" + "---:|" * len(counts))
    lines += [f"| {kind} | " + " | ".join(str(c[kind]) for c in counts.values()) + " |" for kind in kinds]
    return lines


def _step_costs(results: dict[str, tuple[ListingMetrics, list[ListingOutcome]]]) -> list[str]:
    lines = []
    for path, (_, outcomes) in results.items():
        reviewed = [o for o in outcomes if o.error is None and o.step_costs]
        if not reviewed or not path.startswith("agent"):
            continue
        totals: dict[str, float] = defaultdict(float)
        for o in reviewed:
            for step, cost in o.step_costs.items():
                totals[step] += cost
        whole = sum(totals.values()) or 1.0
        lines += [
            "",
            f"**`{path}`: cost per review, by step**",
            "",
            "| Step | cost / review | share |",
            "|---|---:|---:|",
        ]
        lines += [f"| {step} | ${cost / len(reviewed):.4f} | {cost / whole:.0%} |" for step, cost in totals.items()]
    return lines


def _by_listing(path: str, outcomes: list[ListingOutcome]) -> list[str]:
    runs: dict[str, list[ListingOutcome]] = defaultdict(list)
    for o in outcomes:
        runs[o.id].append(o)
    lines = ["", f"**`{path}`: listing by listing**", "", "| Listing | expected | missed | extra | verdict |"]
    lines.append("|---|---|---|---|---|")
    for id, tries in runs.items():
        first, n = tries[0], len(tries)
        if first.must_refuse:
            refused = sum(o.error == o.expected_error for o in tries)
            verdict = "✅ refused" if refused == n else f"❌ refused {refused}/{n}"
            lines.append(f"| `{id}` | refuse: {first.expected_error} | | | {verdict} |")
            continue
        expected = ", ".join(" ".join(r) for r in sorted(first.expected)) or "none"
        missed = _tally([o.expected - o.found for o in tries if o.error is None], n)
        extra = _tally([o.found - o.expected for o in tries if o.error is None], n)
        right = sum(o.verdict == o.expected_verdict for o in tries)
        errors = sorted({o.error for o in tries if o.error})
        wrong = sorted({o.verdict for o in tries if o.verdict and o.verdict != o.expected_verdict})
        share = f" ({n - right}/{n})" if n > 1 else ""
        verdict = "✅" if right == n else f"❌ {', '.join(errors + wrong)}{share}"
        escalated = sum(o.escalated for o in tries)
        flag = (" (escalated)" if n == 1 else f" (escalated {escalated}/{n})") if escalated else ""
        lines.append(f"| `{id}` | {expected} | {missed} | {extra} | {verdict}{flag} |")
    extras = [(o.id, ref, message) for o in outcomes for ref, message in o.notes if ref not in o.expected]
    if extras:
        lines += ["", f"**`{path}`: findings outside the annotation**", ""]
        lines += [f"- `{id}` · {' '.join(ref)}: {message}" for id, ref, message in extras]
    return lines


def _tally(refs_per_run: list[set[LegalRef]], runs: int) -> str:
    """ "LAU 36" in a single run; "LAU 36 (2/3)" when it happened in two runs of three."""
    counts: dict[LegalRef, int] = defaultdict(int)
    for refs in refs_per_run:
        for ref in refs:
            counts[ref] += 1
    return ", ".join(" ".join(ref) + (f" ({k}/{runs})" if runs > 1 else "") for ref, k in sorted(counts.items()))


def save(results: dict[str, tuple[ListingMetrics, list[ListingOutcome]]], run_cost: float) -> pathlib.Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"listings-{stamp}.json"

    def outcome_json(o: ListingOutcome) -> dict[str, Any]:
        data = asdict(o)
        data["expected"] = sorted(" ".join(r) for r in o.expected)
        data["found"] = sorted(" ".join(r) for r in o.found)
        data["notes"] = [{"ref": " ".join(ref), "message": message} for ref, message in o.notes]
        data["read"] = sorted(" ".join(r) for r in o.read)
        data["rejected"] = [{"ref": " ".join(ref) if ref else None, "problem": problem} for ref, problem in o.rejected]
        return data

    document = {
        "measured_at": stamp,
        "llm_model": get_settings().llm_model,
        "run_cost_usd": run_cost,
        "results": {
            p: {"metrics": asdict(m), "outcomes": [outcome_json(o) for o in outs]} for p, (m, outs) in results.items()
        },
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


async def measure(
    paths: tuple[str, ...],
    only: set[str] | None = None,
    cag_prompt: str = PROMPT_VERSION,
    repeat: int = 1,
    critic: bool = True,
) -> tuple[dict[str, tuple[ListingMetrics, list[ListingOutcome]]], float]:
    settings = get_settings()
    cases = [case for case in load_listings() if not only or case.id in only]
    moderation: ModerationClient | None = LiteLLMModeration() if settings.openai_api_key else None
    generator = wrapper_for(settings.llm_model, settings.llm_fallback_model)
    results: dict[str, tuple[ListingMetrics, list[ListingOutcome]]] = {}

    if "cag" in paths:
        pipeline = ListingReviewService(
            llm=generator, moderation=moderation, model=settings.llm_model, prompt_version=cag_prompt
        )
        outcomes = []
        for r in range(1, repeat + 1):
            for case in cases:
                outcomes.append(outcome := await review_with_pipeline(case, pipeline))
                outcome.repeat = r
        results[f"cag {cag_prompt}"] = (summarise(outcomes), outcomes)

    if "agent" in paths:
        if not settings.database_url:
            raise SystemExit("DATABASE_URL is not configured: the agent searches the corpus.")
        engine = create_engine(settings.database_url)
        try:
            search = RetrieverSearch(
                Retriever(
                    session_factory(engine),
                    LiteLLMEmbeddings(model=settings.embedding_model, dimensions=settings.embedding_dimensions),
                    top_k=settings.retrieval_top_k,
                    min_score=settings.retrieval_min_score,
                ),
                top_k=settings.retrieval_top_k,
                min_score=settings.retrieval_min_score,
            )
            agent = AgentReviewService(
                generator,
                search,
                moderation,
                model=settings.llm_model,
                max_iterations=settings.agent_max_iterations,
                timeout_seconds=settings.agent_timeout_seconds,
                max_fragments=settings.agent_max_fragments,
                critic=wrapper_for(settings.llm_judge_model, settings.llm_judge_fallback_model) if critic else None,
                critic_min_confidence=settings.agent_critic_min_confidence,
                critic_escalate_below=settings.agent_critic_escalate_below,
                max_review_attempts=settings.agent_max_review_attempts,
                checkpoints=MemoryCheckpoints(),
                human_review=False,
            )
            outcomes = []
            for r in range(1, repeat + 1):
                for case in cases:
                    outcomes.append(outcome := await review_with_agent(case, agent))
                    outcome.repeat = r
            results["agent" if critic else "agent without critic"] = (summarise(outcomes), outcomes)
        finally:
            await engine.dispose()

    run_cost = sum(o.cost_usd for _, outcomes in results.values() for o in outcomes)
    return results, run_cost


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the listing reviews against the annotated listings.")
    parser.add_argument("--path", choices=[*PATHS, "both"], default="both")
    parser.add_argument("--only", help="Comma-separated listing ids: a cheap run over a few cases")
    parser.add_argument(
        "--cag-prompt", default=PROMPT_VERSION, help="The pipeline's prompt version (listing_review/<v>)"
    )
    parser.add_argument("--repeat", type=int, default=1, help="Review every listing N times: the variance is a result")
    parser.add_argument("--no-critic", action="store_true", help="The agent without its critic: what the critic adds")
    arguments = parser.parse_args()
    paths = PATHS if arguments.path == "both" else (arguments.path,)
    only = set(arguments.only.split(",")) if arguments.only else None

    results, run_cost = asyncio.run(
        measure(paths, only, arguments.cag_prompt, arguments.repeat, critic=not arguments.no_critic)
    )
    print(render(results))
    print(f"\nCost of the run: ${run_cost:.4f}")
    print(f"Saved to {save(results, run_cost)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
