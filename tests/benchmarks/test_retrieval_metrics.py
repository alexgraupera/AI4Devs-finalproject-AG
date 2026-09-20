"""The metrics, and the golden set itself.

These stay hermetic: they measure the measuring, not the retrieval. Running the benchmark for
real needs a corpus and costs a fraction of a cent, which is `make benchmark-retrieval`.
"""

from benchmarks.retrieval.metrics import (
    RetrievedRef,
    is_hit,
    mean_reciprocal_rank,
    no_answer_rate,
    percentile,
    rank_of_first_expected,
    recall_at,
    reciprocal_rank,
)
from benchmarks.retrieval.questions import ExpectedChunk, Question, load_questions

LAU = "BOE-A-1994-26003"


def ref(block_id: str, *, law_id: str = LAU, score: float = 0.7) -> RetrievedRef:
    return RetrievedRef(law_id=law_id, block_id=block_id, score=score)


def a_question(*, expected: list[str] | None = None) -> Question:
    blocks = ["a36"] if expected is None else expected
    return Question(
        id="deposit",
        question="¿Cuál es la fianza?",
        expected=[ExpectedChunk(law_id=LAU, block_id=block) for block in blocks],
        tags=["deposit"],
    )


def an_out_of_domain_question() -> Question:
    return Question(id="ood", question="¿Qué tiempo hará?", expected=[], tags=["out-of-domain"])


def test_finds_the_rank_of_the_expected_article() -> None:
    retrieved = [ref("a20"), ref("a36"), ref("a9")]

    assert rank_of_first_expected(retrieved, a_question().expected) == 2


def test_the_rank_is_unknown_when_the_article_never_came_back() -> None:
    assert rank_of_first_expected([ref("a20")], a_question().expected) is None


def test_the_same_block_id_in_another_law_is_not_the_expected_article() -> None:
    # Block ids repeat across laws: `a36` exists in the LAU and in the Catalan law.
    retrieved = [ref("a36", law_id="BOE-A-2008-3657")]

    assert rank_of_first_expected(retrieved, a_question().expected) is None


def test_a_question_with_several_acceptable_articles_counts_the_first_one() -> None:
    question = a_question(expected=["a9", "a10"])

    assert rank_of_first_expected([ref("a20"), ref("a10")], question.expected) == 2


def test_a_hit_is_anything_inside_the_top_k() -> None:
    retrieved = [ref("a20"), ref("a9"), ref("a36")]

    assert is_hit(retrieved, a_question(), k=3)
    assert not is_hit(retrieved, a_question(), k=2)


def test_the_reciprocal_rank_rewards_being_first() -> None:
    assert reciprocal_rank([ref("a36"), ref("a20")], a_question()) == 1.0
    assert reciprocal_rank([ref("a20"), ref("a36")], a_question()) == 0.5
    assert reciprocal_rank([ref("a20")], a_question()) == 0.0


def test_an_out_of_domain_question_is_correct_when_nothing_comes_back() -> None:
    question = an_out_of_domain_question()

    assert is_hit([], question, k=5)
    assert reciprocal_rank([], question) == 1.0


def test_an_out_of_domain_question_is_wrong_when_something_comes_back() -> None:
    question = an_out_of_domain_question()

    assert not is_hit([ref("a36")], question, k=5)
    assert reciprocal_rank([ref("a36")], question) == 0.0


def test_recall_ignores_the_out_of_domain_questions() -> None:
    # Otherwise a retrieval that returns nothing at all would score 50% recall.
    outcomes = [(a_question(), [ref("a36")]), (an_out_of_domain_question(), [])]

    assert recall_at(outcomes, 5) == 1.0


def test_recall_counts_the_answerable_questions_that_were_found() -> None:
    outcomes = [(a_question(), [ref("a36")]), (a_question(), [ref("a20")])]

    assert recall_at(outcomes, 5) == 0.5


def test_the_mean_reciprocal_rank_averages_over_the_answerable_questions() -> None:
    outcomes = [(a_question(), [ref("a36")]), (a_question(), [ref("a20"), ref("a36")])]

    assert mean_reciprocal_rank(outcomes) == 0.75


def test_the_no_answer_rate_only_looks_at_the_out_of_domain_questions() -> None:
    outcomes = [
        (a_question(), [ref("a36")]),
        (an_out_of_domain_question(), []),
        (an_out_of_domain_question(), [ref("a36")]),
    ]

    assert no_answer_rate(outcomes) == 0.5


def test_metrics_over_an_empty_run_are_zero_rather_than_an_error() -> None:
    assert recall_at([], 5) == 0.0
    assert mean_reciprocal_rank([]) == 0.0
    assert no_answer_rate([]) == 0.0
    assert percentile([], 95) == 0.0


def test_the_percentile_stays_inside_the_measured_values() -> None:
    assert percentile([10.0, 20.0, 30.0], 50) == 20.0
    assert percentile([10.0, 20.0, 30.0], 95) == 30.0


# ── The golden set itself ────────────────────────────────────────────────────────────────────


def test_the_golden_set_parses_and_is_big_enough_to_mean_something() -> None:
    questions = load_questions()

    assert len(questions) >= 25


def test_every_expected_article_points_at_a_source_of_the_corpus() -> None:
    from app.ingestion.sources import CORPUS

    known = {source.source_id for source in CORPUS}
    expected = {chunk.law_id for question in load_questions() for chunk in question.expected}

    assert expected <= known


def test_the_set_covers_the_three_families_it_was_designed_around() -> None:
    tags = {tag for question in load_questions() for tag in question.tags}

    assert {"legal-wording", "paraphrase", "out-of-domain"} <= tags


def test_the_set_has_enough_out_of_domain_questions_to_measure_refusals() -> None:
    out_of_domain = [question for question in load_questions() if question.is_out_of_domain]

    assert len(out_of_domain) >= 5


def test_every_answerable_question_states_what_it_expects() -> None:
    for question in load_questions():
        if not question.is_out_of_domain:
            assert all(chunk.law_id and chunk.block_id for chunk in question.expected), question.id
