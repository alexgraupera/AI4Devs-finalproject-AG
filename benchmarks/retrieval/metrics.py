"""The numbers a retrieval change has to move before it is worth keeping.

**recall@k**: did any of the expected articles make it into the top k? For a question with one
right answer, that is what decides whether the generation can possibly be correct: an article
that was never retrieved cannot be cited.

**MRR**: how high did the first expected article land. Recall says "it was somewhere in the
five"; MRR says whether it was first or fifth, which is what the context budget and the model's
attention actually care about.

**No-answer rate**: over the out-of-domain questions, how often the retrieval correctly returns
nothing. Without it, any change that lowers the threshold would look like an improvement.
"""

from dataclasses import dataclass

from benchmarks.retrieval.questions import ExpectedChunk, Question


@dataclass(frozen=True)
class RetrievedRef:
    """What the benchmark needs from a result: which article it is, and its score."""

    law_id: str
    block_id: str
    score: float


def rank_of_first_expected(retrieved: list[RetrievedRef], expected: list[ExpectedChunk]) -> int | None:
    """1-based rank of the first expected article, or None when none was retrieved."""
    wanted = {(chunk.law_id, chunk.block_id) for chunk in expected}
    for position, result in enumerate(retrieved, start=1):
        if (result.law_id, result.block_id) in wanted:
            return position
    return None


def is_hit(retrieved: list[RetrievedRef], question: Question, k: int) -> bool:
    if question.is_out_of_domain:
        # Correct means nothing came back: there is nothing in the corpus to find.
        return not retrieved
    rank = rank_of_first_expected(retrieved[:k], question.expected)
    return rank is not None


def reciprocal_rank(retrieved: list[RetrievedRef], question: Question) -> float:
    if question.is_out_of_domain:
        return 1.0 if not retrieved else 0.0
    rank = rank_of_first_expected(retrieved, question.expected)
    return 1 / rank if rank is not None else 0.0


def recall_at(outcomes: list[tuple[Question, list[RetrievedRef]]], k: int) -> float:
    answerable = [(question, retrieved) for question, retrieved in outcomes if not question.is_out_of_domain]
    if not answerable:
        return 0.0
    return sum(is_hit(retrieved, question, k) for question, retrieved in answerable) / len(answerable)


def mean_reciprocal_rank(outcomes: list[tuple[Question, list[RetrievedRef]]]) -> float:
    answerable = [(question, retrieved) for question, retrieved in outcomes if not question.is_out_of_domain]
    if not answerable:
        return 0.0
    return sum(reciprocal_rank(retrieved, question) for question, retrieved in answerable) / len(answerable)


def no_answer_rate(outcomes: list[tuple[Question, list[RetrievedRef]]]) -> float:
    """Share of the out-of-domain questions that correctly retrieved nothing."""
    unanswerable = [retrieved for question, retrieved in outcomes if question.is_out_of_domain]
    if not unanswerable:
        return 0.0
    return sum(not retrieved for retrieved in unanswerable) / len(unanswerable)


def percentile(values: list[float], percent: int) -> float:
    """Nearest-rank percentile: with a few dozen questions, interpolating invents precision."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, -(-percent * len(ordered) // 100))
    return ordered[rank - 1]
