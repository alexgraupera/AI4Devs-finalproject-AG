"""The regression gate: what fails, what passes, and what it refuses to compare."""

import json
import pathlib

import pytest

from evals.gate import Direction, Threshold, compare, promote, read_answers, read_listings, read_run

QUALITY = Threshold("listings.f1", Direction.HIGHER, 0.05)
SAFETY = Threshold("listings.adversarial_handled", Direction.HIGHER, zero_tolerance=True)
INVENTED = Threshold("listings.dropped_findings", Direction.LOWER, zero_tolerance=True)
COST = Threshold("listings.cost_per_review_usd", Direction.LOWER, 0.25, relative=True)


def test_a_drop_within_the_tolerance_passes() -> None:
    assert compare({"listings.f1": 0.86}, {"listings.f1": 0.90}, (QUALITY,)).passed


def test_a_drop_beyond_the_tolerance_fails() -> None:
    result = compare({"listings.f1": 0.84}, {"listings.f1": 0.90}, (QUALITY,))

    assert [b.metric for b in result.breaches] == ["listings.f1"]
    assert "tolerance 5 points" in result.breaches[0].reason


def test_any_drop_on_a_zero_tolerance_metric_fails() -> None:
    assert not compare({"listings.adversarial_handled": 0.75}, {"listings.adversarial_handled": 1.0}, (SAFETY,)).passed
    assert not compare({"listings.dropped_findings": 1}, {"listings.dropped_findings": 0}, (INVENTED,)).passed


def test_an_improvement_never_fails() -> None:
    thresholds = (QUALITY, SAFETY, INVENTED, COST)
    baseline = {
        "listings.f1": 0.7,
        "listings.adversarial_handled": 0.75,
        "listings.dropped_findings": 2,
        "listings.cost_per_review_usd": 0.002,
    }
    better = {
        "listings.f1": 0.9,
        "listings.adversarial_handled": 1.0,
        "listings.dropped_findings": 0,
        "listings.cost_per_review_usd": 0.001,
    }

    assert compare(better, baseline, thresholds).passed


def test_a_metric_missing_from_the_run_fails_instead_of_passing_silently() -> None:
    result = compare({}, {"listings.f1": 0.9}, (QUALITY,))

    assert not result.passed
    assert "missing from the run" in result.breaches[0].reason


def test_a_cost_is_compared_as_a_share_of_the_baseline() -> None:
    baseline = {"listings.cost_per_review_usd": 0.0020}

    assert compare({"listings.cost_per_review_usd": 0.0024}, baseline, (COST,)).passed
    assert not compare({"listings.cost_per_review_usd": 0.0026}, baseline, (COST,)).passed


# ── Reading the runs ────────────────────────────────────────────────────────────────────────


def answers_run(tmp_path: pathlib.Path, *, judged: bool = True, tags: list[str] | None = None) -> pathlib.Path:
    metrics = {
        "questions": 32,
        "refusal_rate": 1.0,
        "faithfulness": 0.9 if judged else 0.0,
        "relevance": 0.95 if judged else 0.0,
        "correctness": 0.76 if judged else 0.0,
        "opening_consistency": 0.91 if judged else 0.0,
        "cost_by_stage_usd": {"generation": 0.005},
    }
    document = {
        "llm_model": "anthropic/claude-haiku-4-5",
        "judge_model": "openai/gpt-5.4-mini",
        "judged": judged,
        "tags": tags or [],
        "results": [{"variant": {"name": "baseline"}, "metrics": metrics}],
    }
    path = tmp_path / "answers-1.json"
    path.write_text(json.dumps(document))
    return path


def listings_run(tmp_path: pathlib.Path, *, only: list[str] | None = None) -> pathlib.Path:
    metrics = {"f1": 0.9, "clean_false_positive_rate": 0.0, "adversarial_handled": 1.0, "dropped_findings": 0}
    document = {
        "llm_model": "anthropic/claude-haiku-4-5",
        "only": only or [],
        "results": {"cag v3": {"metrics": metrics}, "agent": {"metrics": {"f1": 0.6}}},
    }
    path = tmp_path / "listings-1.json"
    path.write_text(json.dumps(document))
    return path


def test_a_run_without_the_judge_has_no_judge_metrics_rather_than_zeros(tmp_path: pathlib.Path) -> None:
    metrics, _ = read_answers(answers_run(tmp_path, judged=False))

    assert metrics["answers.faithfulness"] is None
    assert metrics["answers.refusal_rate"] == 1.0
    assert "answers.cost_by_stage_usd" not in metrics


def test_a_subset_is_not_gated(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="subset"):
        read_answers(answers_run(tmp_path, tags=["regression"]))
    with pytest.raises(ValueError, match="subset"):
        read_listings(listings_run(tmp_path, only=["clean-valencia"]))


def test_the_listings_gated_are_the_pipeline_s_not_the_agent_s(tmp_path: pathlib.Path) -> None:
    metrics, models = read_listings(listings_run(tmp_path))

    assert metrics["listings.f1"] == 0.9
    assert models["listings.path"] == "cag v3"


def test_a_promoted_baseline_keeps_only_the_gated_metrics_and_where_they_came_from(tmp_path: pathlib.Path) -> None:
    run = read_run(answers_run(tmp_path), listings_run(tmp_path))
    baseline = tmp_path / "baseline.json"

    document = promote(run, baseline)

    assert document["sources"] == {"answers": "answers-1.json", "listings": "listings-1.json"}
    assert "answers.questions" not in document["metrics"]
    assert compare(run.metrics, json.loads(baseline.read_text())["metrics"], ()).passed
