"""`make benchmark-retrieval`: run every retrieval variant over the golden set and compare them.

Every technique goes through this same harness, so "hybrid search is better" stops being an
opinion and becomes a row in a table. Phase #25 registers its variants here and keeps only what
moves these numbers.

    python -m benchmarks.retrieval.run
    python -m benchmarks.retrieval.run --variant dense-k5-t0.5
"""

import argparse
import asyncio
import json
import pathlib
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from app.config import get_settings
from app.foundation.persistence.database import create_engine, session_factory
from app.generation.rag.embeddings import PRICE_PER_MILLION_TOKENS, LiteLLMEmbeddings
from app.generation.rag.retriever import Retriever
from benchmarks.retrieval.metrics import (
    RetrievedRef,
    mean_reciprocal_rank,
    no_answer_rate,
    percentile,
    rank_of_first_expected,
    recall_at,
)
from benchmarks.retrieval.questions import Question, load_questions

RESULTS_DIR = pathlib.Path(__file__).parent / "results"
REPORTED_K = (1, 3, 5)


@dataclass(frozen=True)
class RetrievalVariant:
    """A named retrieval configuration. Phase #25 adds its flags here."""

    name: str
    k: int = 5
    min_score: float = 0.5


@dataclass
class QuestionOutcome:
    id: str
    question: str
    tags: list[str]
    retrieved: list[str]
    expected: list[str]
    rank: int | None
    top_score: float | None
    latency_ms: int


@dataclass
class BenchmarkResult:
    variant: str
    k: int
    min_score: float
    questions: int
    recall: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    no_answer_rate: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    estimated_cost_usd_per_query: float = 0.0
    outcomes: list[QuestionOutcome] = field(default_factory=list)


# The variants measured today. Only `dense` exists: the k and threshold sweep is what tunes the
# defaults, and #25 adds reformulation, hybrid and reranking next to them.
VARIANTS: tuple[RetrievalVariant, ...] = (
    RetrievalVariant(name="dense-k5-t0.5", k=5, min_score=0.5),
    RetrievalVariant(name="dense-k5-t0.3", k=5, min_score=0.3),
    RetrievalVariant(name="dense-k5-t0.45", k=5, min_score=0.45),
    RetrievalVariant(name="dense-k5-t0.55", k=5, min_score=0.55),
    RetrievalVariant(name="dense-k3-t0.5", k=3, min_score=0.5),
    RetrievalVariant(name="dense-k10-t0.5", k=10, min_score=0.5),
)


async def run(variant: RetrievalVariant, questions: list[Question], retriever: Retriever) -> BenchmarkResult:
    outcomes: list[QuestionOutcome] = []
    pairs: list[tuple[Question, list[RetrievedRef]]] = []
    latencies: list[float] = []

    for question in questions:
        started = time.perf_counter()
        chunks = await retriever.search(question.question, k=variant.k, min_score=variant.min_score)
        latency = (time.perf_counter() - started) * 1000
        latencies.append(latency)

        refs = [RetrievedRef(law_id=c.law_id, block_id=c.block_id, score=c.score) for c in chunks]
        pairs.append((question, refs))
        outcomes.append(
            QuestionOutcome(
                id=question.id,
                question=question.question,
                tags=question.tags,
                retrieved=[f"{ref.law_id}#{ref.block_id}" for ref in refs],
                expected=[f"{e.law_id}#{e.block_id}" for e in question.expected],
                rank=rank_of_first_expected(refs, question.expected) if question.expected else None,
                top_score=round(refs[0].score, 4) if refs else None,
                latency_ms=int(latency),
            )
        )

    return BenchmarkResult(
        variant=variant.name,
        k=variant.k,
        min_score=variant.min_score,
        questions=len(questions),
        recall={k: recall_at(pairs, k) for k in REPORTED_K if k <= variant.k},
        mrr=mean_reciprocal_rank(pairs),
        no_answer_rate=no_answer_rate(pairs),
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        outcomes=outcomes,
    )


def render(results: list[BenchmarkResult]) -> str:
    header = [
        "| Variant | k | threshold | "
        + " | ".join(f"recall@{k}" for k in REPORTED_K)
        + " | MRR | no-answer | p50 | p95 |"
    ]
    header.append("|---|---:|---:|" + "---:|" * (len(REPORTED_K) + 4))

    for result in results:
        recalls = " | ".join(f"{result.recall[k]:.0%}" if k in result.recall else "—" for k in REPORTED_K)
        header.append(
            f"| `{result.variant}` | {result.k} | {result.min_score} | {recalls} | {result.mrr:.3f} "
            f"| {result.no_answer_rate:.0%} | {result.p50_latency_ms:.0f} ms | {result.p95_latency_ms:.0f} ms |"
        )

    misses = [
        f"- `{outcome.id}` ({', '.join(outcome.tags)}): expected {outcome.expected}, "
        + (
            f"found at rank {outcome.rank}"
            if outcome.rank
            else f"not retrieved (top: {outcome.retrieved[:2] or 'nothing'})"
        )
        for result in results[:1]
        for outcome in result.outcomes
        if outcome.expected and outcome.rank != 1
    ]
    if misses:
        header += ["", f"**Where `{results[0].variant}` does not rank the right article first**", *misses]

    false_positives = [
        f"- `{outcome.id}`: retrieved {outcome.retrieved[:2]} (top score {outcome.top_score})"
        for result in results[:1]
        for outcome in result.outcomes
        if not outcome.expected and outcome.retrieved
    ]
    if false_positives:
        header += ["", f"**Out-of-domain questions `{results[0].variant}` answered anyway**", *false_positives]

    return "\n".join(header)


def save(results: list[BenchmarkResult]) -> pathlib.Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "measured_at": stamp,
                "embedding_model": get_settings().embedding_model,
                "results": [asdict(result) for result in results],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


async def measure(variants: tuple[RetrievalVariant, ...]) -> list[BenchmarkResult]:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured: there is no corpus to measure against.")

    questions = load_questions()
    engine = create_engine(settings.database_url)
    client = LiteLLMEmbeddings(model=settings.embedding_model, dimensions=settings.embedding_dimensions)
    try:
        results = []
        for variant in variants:
            retriever = Retriever(session_factory(engine), client, top_k=variant.k, min_score=variant.min_score)
            result = await run(variant, questions, retriever)
            # The query cost is the embedding of the question: the same for every variant, so it
            # is attributed per run rather than pretending each variant has its own.
            price = PRICE_PER_MILLION_TOKENS.get(client.model, 0.0)
            result.estimated_cost_usd_per_query = client.tokens / 1_000_000 * price / max(len(questions), 1)
            results.append(result)
        return results
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the retrieval over the golden question set.")
    parser.add_argument("--variant", action="append", default=[], help="Run only these variants by name")
    arguments = parser.parse_args()

    chosen = tuple(v for v in VARIANTS if v.name in arguments.variant) if arguments.variant else VARIANTS
    if not chosen:
        raise SystemExit(f"No variant matched. Available: {', '.join(v.name for v in VARIANTS)}")

    results = asyncio.run(measure(chosen))
    print(render(results))
    print(f"\nSaved to {save(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
