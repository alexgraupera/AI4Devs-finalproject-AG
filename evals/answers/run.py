"""`make eval-answers`: run the golden questions through the real Q&A service and judge the answers.

Every question goes through `RegulationQAService` exactly as a request would (guardrails,
retrieval, reranking, generation, citation checks, grounding), then a judge on the other provider
grades what came back. The same questions under two configurations are an A/B: that is how a prompt
change stops being an opinion.

    python -m evals.answers.run                       # every variant
    python -m evals.answers.run --variant baseline    # one of them
    python -m evals.answers.run --no-judge            # labels only, no judge cost

It needs the corpus ingested and embedded, and costs about $0.02 per question (the service's calls
plus the judge's). The report goes to stdout and, with every answer, to `evals/results/`.
"""

import argparse
import asyncio
import json
import pathlib
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.config import get_settings
from app.domain.regulation_qa_service import RegulationQAService
from app.domain.schemas.regulation_answer import AnsweredQuestion, RegulationQuestion
from app.foundation.guardrails.input import InputGuardrailViolation, ModerationClient
from app.foundation.guardrails.moderation import LiteLLMModeration
from app.foundation.llm.wrapper import LLMWrapper, StructuredLLM, build_router
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.rag.context import build_context
from app.generation.rag.embeddings import PRICE_PER_MILLION_TOKENS, LiteLLMEmbeddings
from app.generation.rag.rerank import Reranker
from app.generation.rag.retriever import Retriever
from benchmarks.retrieval.questions import Question, load_questions
from evals.answers.judge import judge_answer
from evals.answers.metrics import AnswerMetrics, AnswerOutcome, regression_passed, summarise
from evals.recording import RecordingLLM, cost_by_stage

RESULTS_DIR = pathlib.Path(__file__).parents[1] / "results"

# The judge runs on the other provider from the generator, so it does not share its blind spots.
JUDGE_MODEL = "openai/gpt-5.4-mini"
JUDGE_FALLBACK_MODEL = "anthropic/claude-haiku-4-5"


@dataclass(frozen=True)
class AnswerVariant:
    """A named configuration of the Q&A service: what an A/B compares."""

    name: str
    prompt_version: str = "v2"
    rerank: bool = True


# `prompt-v1` is the prompt before the fix of #34: it is here so the regression case has a
# configuration it is expected to fail on, which is what proves the case can catch the bug.
VARIANTS: tuple[AnswerVariant, ...] = (
    AnswerVariant(name="baseline"),
    AnswerVariant(name="prompt-v1", prompt_version="v1"),
)


class QAService(Protocol):
    async def ask(self, question: RegulationQuestion) -> AnsweredQuestion: ...


async def evaluate(
    questions: list[Question],
    service: QAService,
    recording: RecordingLLM,
    judge: StructuredLLM | None,
    *,
    max_context_chars: int,
) -> list[AnswerOutcome]:
    return [await _evaluate(question, service, recording, judge, max_context_chars) for question in questions]


async def _evaluate(
    question: Question,
    service: QAService,
    recording: RecordingLLM,
    judge: StructuredLLM | None,
    max_context_chars: int,
) -> AnswerOutcome:
    expected = [f"{chunk.law_id}#{chunk.block_id}" for chunk in question.expected]
    recording.drain()
    started = time.perf_counter()

    try:
        answered = await service.ask(RegulationQuestion(question=question.question))
    except InputGuardrailViolation as violation:
        recording.drain()
        return AnswerOutcome(
            id=question.id,
            question=question.question,
            tags=question.tags,
            expected=expected,
            answered=False,
            rejected_by=violation.reason,
        )
    except Exception as error:
        # A provider failing is an outcome of the run, recorded as a wrong answer, not a crash of it.
        return AnswerOutcome(
            id=question.id,
            question=question.question,
            tags=question.tags,
            expected=expected,
            answered=False,
            error=f"{type(error).__name__}: {error}",
            cost_by_stage=cost_by_stage(recording.drain()),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    context = build_context(answered.retrieved, max_chars=max_context_chars)
    block_of = {chunk.chunk_id: f"{chunk.law_id}#{chunk.block_id}" for chunk in answered.retrieved}
    outcome = AnswerOutcome(
        id=question.id,
        question=question.question,
        tags=question.tags,
        expected=expected,
        answered=answered.answer.has_answer,
        answer=answered.answer.answer,
        cited=[block_of.get(citation.chunk_id, f"{citation.law_id}#?") for citation in answered.answer.citations],
        in_context=[f"{chunk.law_id}#{chunk.block_id}" for chunk in context.chunks],
        cost_by_stage=cost_by_stage(recording.drain()),
        latency_ms=latency_ms,
    )

    if judge is not None and outcome.answered and question.reference:
        outcome.judged = await judge_answer(
            judge, question=question.question, reference=question.reference, context=context.text, answer=outcome.answer
        )
        judge_usage = outcome.judged.usage
        outcome.cost_by_stage["eval_judge"] = float(judge_usage.estimated_cost_usd or 0) if judge_usage else 0.0
    return outcome


def render(results: list[tuple[AnswerVariant, AnswerMetrics, list[AnswerOutcome]]]) -> str:
    lines = [
        "| Variant | answered | refused (out of domain) | cites expected | context recall | faithfulness "
        "| relevance | correctness | opening holds | regressions | cost / question | p50 | p95 |",
        "|---|" + "---:|" * 12,
    ]
    for variant, m, _ in results:
        lines.append(
            f"| `{variant.name}` | {m.answered_rate:.0%} | {m.refusal_rate:.0%} | {m.citation_accuracy:.0%} "
            f"| {m.context_recall:.0%} | {m.faithfulness:.2f} | {m.relevance:.2f} | {m.correctness:.2f} "
            f"| {m.opening_consistency:.0%} | {m.regressions_passed}/{m.regressions} "
            f"| ${m.cost_per_question_usd:.4f} | {m.p50_latency_ms / 1000:.1f} s | {m.p95_latency_ms / 1000:.1f} s |"
        )

    for variant, metrics, outcomes in results:
        lines += ["", f"**`{variant.name}`: cost per question by stage**", ""]
        lines += [f"- {stage}: ${cost:.4f}" for stage, cost in metrics.cost_by_stage_usd.items()]
        findings = _findings(outcomes)
        if findings:
            lines += ["", f"**`{variant.name}`: what to look at**", "", *findings]
    return "\n".join(lines)


def _findings(outcomes: list[AnswerOutcome]) -> list[str]:
    findings = []
    for o in outcomes:
        if o.error:
            findings.append(f"- `{o.id}`: failed ({o.error[:120]})")
        elif o.answerable and not o.answered:
            findings.append(f"- `{o.id}`: answerable, refused")
        elif not o.answerable and o.answered:
            findings.append(f"- `{o.id}`: **out of domain, answered anyway**")
        elif o.answered and o.judged is not None:
            problems = []
            if o.judged.correctness < 1:
                problems.append(f"correctness {o.judged.correctness}")
            if o.judged.unsupported:
                problems.append(f"unsupported: {'; '.join(o.judged.unsupported)[:160]}")
            if not o.judged.opening_holds:
                problems.append("the opening does not hold")
            if not o.cites_expected:
                problems.append(f"cites {o.cited}, expected {o.expected}")
            if problems:
                findings.append(f"- `{o.id}`: {', '.join(problems)}. _{o.judged.analysis[:200]}_")
        if o.is_regression and not regression_passed(o):
            findings.append(f"- `{o.id}`: **regression case failed**")
    return findings


def save(results: list[tuple[AnswerVariant, AnswerMetrics, list[AnswerOutcome]]], *, run_cost: float) -> pathlib.Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    settings = get_settings()
    path = RESULTS_DIR / f"answers-{stamp}.json"
    document = {
        "measured_at": stamp,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "judge_model": JUDGE_MODEL,
        "run_cost_usd": run_cost,
        "results": [
            {"variant": asdict(variant), "metrics": asdict(metrics), "outcomes": [asdict(o) for o in outcomes]}
            for variant, metrics, outcomes in results
        ],
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path


async def measure(
    variants: tuple[AnswerVariant, ...], *, judge_model: str | None
) -> tuple[list[tuple[AnswerVariant, AnswerMetrics, list[AnswerOutcome]]], float]:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured: there is no corpus to answer from.")

    questions = load_questions()
    engine = create_engine(settings.database_url)
    embeddings = LiteLLMEmbeddings(model=settings.embedding_model, dimensions=settings.embedding_dimensions)
    generator = RecordingLLM(
        LLMWrapper(
            router=build_router(settings.llm_model, settings.llm_fallback_model or None, settings.llm_max_retries),
            max_retries=settings.llm_max_retries,
        )
    )
    judge = (
        LLMWrapper(
            router=build_router(judge_model, JUDGE_FALLBACK_MODEL, settings.llm_max_retries),
            max_retries=settings.llm_max_retries,
        )
        if judge_model
        else None
    )
    moderation: ModerationClient | None = LiteLLMModeration() if settings.openai_api_key else None

    try:
        results = []
        for variant in variants:
            # No cache and no spend guard: an evaluation that reads a cache measures the cache (S5).
            service = RegulationQAService(
                llm=generator,
                retriever=Retriever(
                    session_factory(engine),
                    embeddings,
                    top_k=settings.retrieval_top_k,
                    min_score=settings.retrieval_min_score,
                ),
                moderation=moderation,
                reranker=Reranker(generator, top_n=settings.retrieval_top_k) if variant.rerank else None,
                check_claims=settings.grounding_enabled,
                min_confidence=settings.grounding_min_confidence,
                model=settings.llm_model,
                prompt_version=variant.prompt_version,
                top_k=settings.retrieval_top_k,
                rerank_pool=settings.rerank_pool,
                max_context_chars=settings.max_context_chars,
            )
            outcomes = await evaluate(
                questions, service, generator, judge, max_context_chars=settings.max_context_chars
            )
            results.append((variant, summarise(outcomes), outcomes))
    finally:
        await engine.dispose()

    embedding_cost = embeddings.tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS.get(embeddings.model, 0.0)
    run_cost = embedding_cost + sum(sum(o.cost_by_stage.values()) for _, _, outcomes in results for o in outcomes)
    return results, run_cost


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the regulation answers over the golden set.")
    parser.add_argument("--variant", action="append", default=[], help="Run only these variants by name")
    parser.add_argument("--judge-model", default=JUDGE_MODEL, help="Model that grades the answers")
    parser.add_argument("--no-judge", action="store_true", help="Only the label-based metrics, no judge calls")
    arguments = parser.parse_args()

    chosen = tuple(v for v in VARIANTS if v.name in arguments.variant) if arguments.variant else VARIANTS
    if not chosen:
        raise SystemExit(f"No variant matched. Available: {', '.join(v.name for v in VARIANTS)}")

    results, run_cost = asyncio.run(measure(chosen, judge_model=None if arguments.no_judge else arguments.judge_model))
    print(render(results))
    print(f"\nCost of the run: ${run_cost:.4f}")
    print(f"Saved to {save(results, run_cost=run_cost)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
