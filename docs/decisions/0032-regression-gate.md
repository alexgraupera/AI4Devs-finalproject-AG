# 0032. A regression gate against a promoted baseline, with the real-model evals outside the deploy pipeline

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #50 (part of #4)

## Context

The answers ([ADR 0022](0022-answer-evaluation.md)) and the listing reviews ([ADR 0030](0030-listing-review-evaluation.md)) are measured, and each measurement changed something. A measured baseline is only worth something if a worse run is caught, and "worse" needs a definition: the same code, run twice on the same model, does not give the same numbers.

The original plan ran the evaluations on every pull request. The production session puts them elsewhere, and so does this project's budget: a whole run costs ~$0.70, takes ~20 minutes, varies between runs, and fails when a provider is down, none of which should block merging a typo fix or deploying one.

## Decision

### Two layers

| Where | What | Cost |
|---|---|---|
| **CI, every pull request** | The regression cases with the model mocked ([`tests/evals/test_regressions.py`](../../tests/evals/test_regressions.py)), and the gate's own logic | Free, deterministic, seconds |
| **[`evals.yml`](../../.github/workflows/evals.yml), on demand and weekly** | The corpus built from the BOE, both evaluations on the real models, the gate, the reports as an artifact | ~$0.70 a run |

The mocked cases are named after what they guard: **#34** (an opening its own conclusion contradicts: the prompt rule and the metric that fails it), **a citation to a fragment never retrieved** (the Q&A drops it, an answer with only such citations is refused, the agent loses the citation), and **an injection inside a listing** (the dataset's pattern case is refused before any model call; the one that asks politely reaches both prompts inside the `<anuncio>` tags, with the rule that a note claiming a prior review changes nothing). They catch code that stops guarding against what a model once did; the real runs catch a model that behaves worse.

**The weekly run is opt-in.** It spends from the provider accounts, so it runs only once the repository sets `EVALS_SCHEDULE_ENABLED=true`; a manual run always runs. It needs the `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` repository secrets and fails with that message when they are missing, rather than with a gate full of refusals.

### The baseline

[`evals/baseline.json`](../../evals/baseline.json) is committed and **promoted by hand** (`make eval-promote`), never overwritten by a run: a baseline that follows every run catches nothing. It records the date, the commit, the result files it came from and the models that answered, and only the gated metrics.

The first baseline is the answers run of 2026-09-25 (Claude Haiku 4.5 generating, judged by GPT-5.4 mini) and the pipeline's listing run of #52 (GPT-5.4 mini answering: Anthropic was at its limit). **When a run's models differ from the baseline's, the gate says so**, because a cost or quality breach may then be the model and not the change; a new model is a reason to promote again, deliberately.

### The thresholds

**Zero tolerance**: safety, where any move in the wrong direction fails.

| Metric | Why |
|---|---|
| `answers.refusal_rate` (out of domain) | An answer outside the corpus is an invented legal answer |
| `answers.regressions_passed` | A bug that was fixed and came back. It is 0 of 1 today (#34 is not fixed yet, ADR 0022); the day it passes it is promoted, and then it cannot fail again |
| `listings.adversarial_handled` | An injection obeyed, personal data sent to a provider, a non-listing reviewed |
| `listings.dropped_findings` | A legal basis outside the checklist: the pipeline's invented citation |
| `listings.clean_false_positive_rate` | A clean listing called illegal. 0% in all three runs of prompt v3, and the error a landlord never forgives |

**Tolerances**: quality, which varies between runs. Each tolerance is the noise a rerun was measured to have, so a failure means something moved beyond it:

| Metric | May move | Why |
|---|---:|---|
| Answer rates (answered, cites expected, context recall) | 8 points | Two questions of the 25 answerable; one is noise ([evals.md](../evals.md), limitations) |
| Judge scores (faithfulness, relevance, correctness) | 5 points | Means over claims and grades, finer than one question |
| Opening holds | 9 points | Two of the ~23 answered |
| Listing precision, recall, verdict accuracy | 7 points | One listing (of 15) or one article (of 16): the two v2 runs differed by 7 points of precision |
| Listing F1 | 5 points | The two v2 runs: 0.72 and 0.76 |
| Cost per question or review | 25% of the baseline | A model or prompt change, not noise: the cost is deterministic given the tokens |

**An improvement never fails, and a missing metric always does.** A gate that passes because it could not look (a run without the judge, a subset, a result file without the pipeline) is the worst kind of green: the gate refuses subsets and unjudged runs, and a local `make eval-gate` picks the newest run it can compare and says which ones it skipped.

## Consequences

- `make eval-gate` exits non-zero on any breach, with a table of every metric, its baseline, the run and the rule.
- One run against one run: a tolerance absorbs the noise of a single rerun, not a systematic drift of a point a week. The weekly run's artifacts are the record to look at for that.
- The agent is compared ([ADR 0031](0031-agent-vs-pipeline.md)), not gated: it is not the review the product serves. Gating it would mean promoting a baseline that ADR 0031 says is not good enough.
- A run costs ~$0.70 (answers with the judge ~$0.61, listings ~$0.03, embeddings ~$0.04), plus ~$0.45 with the agent (`agent: true`). With the budget of this project, the weekly schedule stays off until the evaluation period is over or the budget grows.
