# Evaluation

How the quality of the system is measured, what the numbers are today, and every change the numbers decided. The decisions themselves are in [`docs/decisions/`](decisions/); this page gathers the measurements.

## What is measured, and where

| Layer | Question it answers | Command | Status |
|---|---|---|---|
| Retrieval | Does the right article reach the model? | `make benchmark-retrieval` | ✅ [ADR 0012](decisions/0012-retrieval-baseline-and-tuning.md) |
| Answers | Is the answer faithful, relevant, correct, and does it refuse what the corpus does not cover? | `make eval-answers` | ✅ [ADR 0022](decisions/0022-answer-evaluation.md) |
| Semantic cache | Would a similarity threshold serve the right review? | `make benchmark-semantic-cache` | ✅ [ADR 0019](decisions/0019-no-semantic-cache.md) |
| Listing reviews | Which defects does a review find, and which does it invent? | `make eval-listings` | 🔜 #49 |
| Regression gate | Did a change make anything worse? | `make eval-gate` | 🔜 #50 |
| Agent vs pipeline | What does the agent buy for its extra calls? | | 🔜 #52 |

Tests never call a model; these commands are the only code that does. None of them runs in the deploy pipeline.

## The golden set

[`benchmarks/retrieval/questions.yaml`](../benchmarks/retrieval/questions.yaml): **32 questions**, one file for retrieval and answers.

| Family | Questions | What it catches |
|---|---:|---|
| `legal-wording`: phrased as the law phrases it | 10 | The floor: if these fail, nothing else matters |
| `paraphrase`: phrased as a landlord asks | 15 | The user's words are not the law's; includes two stressed-area lookups by town name |
| `conflict`: state and Catalan rules differ | 2 | Answers that mix two jurisdictions into one rule |
| `regression`: bugs found by hand | 1 | #34, an answer whose opening its own conclusion contradicted |
| `out-of-domain` | 7 | Includes one near the domain (home insurance) and one prompt injection |

Every answerable question names the articles that answer it (by law and block, never by chunk id, which changes on every ingestion) and carries a **reference answer written from the text of those articles as ingested**. A test fails if an answerable question has no reference.

## Metrics

**Retrieval** (from the labels): recall@k, MRR, and the share of out-of-domain questions that retrieve nothing.

**Answers** (RAGAS-style, [ADR 0022](decisions/0022-answer-evaluation.md)):

| Metric | Over | From |
|---|---|---|
| Answered | answerable questions | labels |
| Refused | out-of-domain questions; a guardrail rejection counts | labels |
| Cites expected | answerable: an expected article among the citations | labels |
| Context recall | answerable: an expected article in the context the model read | labels |
| Faithfulness | answered: share of legal claims the context supports | judge |
| Relevance | answered: `yes` 1, `partly` 0.5, `no` 0 | judge |
| Correctness | answerable, a refusal scoring 0: against the reference | judge |
| Opening holds | answered: the first sentence survives the rest | judge |
| Regressions | cases tagged `regression`: answered, cites the expected article, opening holds, correctness ≥ 0.5 | both |
| Cost and latency | per question, and per stage (rerank, generation, grounding) | recorded |

Context precision is not measured: it needs every retrieved chunk labelled, and the set labels only the articles that answer each question.

## The judge

- **Model**: GPT-5.4 mini, falling back to Claude Haiku 4.5: the other provider from the one that writes the answers.
- **Rubric**: [`app/foundation/prompts/eval_answer_judge/v1/system.j2`](../app/foundation/prompts/eval_answer_judge/v1/system.j2). Three levels with an example each; the judge writes a short analysis before grading, and the analysis is kept with every grade in the results file.
- **Counting is code**: the judge lists claims and grades; faithfulness and the scores are computed.
- **Known weakness**: it is a model. The grounding judge of [ADR 0014](decisions/0014-grounding-and-retrieval-security.md) was wrong in both directions on 22 questions. Doubtful grades are read, not averaged away.

## Results

### Answers: first run, 2026-09-25

`make eval-answers`, both variants, the 32 questions through the real service (Claude Haiku 4.5 generating, `text-embedding-3-large` at 0.40, reranking and grounding on), judged by GPT-5.4 mini.

| Variant | Answered | Refused (out of domain) | Cites expected | Context recall | Faithfulness | Relevance | Correctness | Opening holds | Regressions | Cost / question | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`baseline`** (Q&A prompt v2) | **92%** | **100%** | **88%** | 100% | 0.90 | 0.96 | **0.76** | 91% | **0/1** | $0.0164 | 9.1 s | 14.9 s |
| `prompt-v1` (before #34) | 84% | 100% | 76% | 100% | 0.95 | 0.95 | 0.68 | 100% | 0/1 | $0.0107 | 6.3 s | 11.5 s |

Where an answer's cost goes (baseline, per question):

| Stage | Cost | Share |
|---|---:|---:|
| Reranking (twenty articles read) | $0.0077 | 47% |
| Generation | $0.0051 | 31% |
| Grounding check | $0.0036 | 22% |
| _Evaluation judge (not a product cost)_ | _$0.0026_ | |

A full run of both variants cost **$1.02**.

**What it says:**

- **The regression case fails, and it is the finding of this run.** The fix of #34 was checked by hand on one answer; measured, prompt v2 still opens "Tu casero no puede exigirte 3 meses de fianza como cantidad obligatoria" before explaining that one month of deposit plus two of additional guarantee is allowed. The same pattern appears in `renewal-paraphrase` (a "No" that the answer then qualifies). Prompt v1 refuses the question outright, which fails too. The fix is incomplete, and the next prompt version is measured against this row.
- **v2 is the better prompt anyway**: it answers 8 points more and cites the expected article 12 points more often, at the price of longer answers (the cost difference is mostly answering instead of refusing).
- **Correctness 0.76** loses most of its points to answers that are right but wander: the other jurisdiction added to a question about one, or a neighbouring article cited instead of the one asked about (`catalan-offer-paraphrase` cites articles 58-59 on advertising instead of 61 on the offer). Two answerable questions are refused.
- **Nothing out of domain gets through**, and the context always contains an expected article (context recall 100%): the losses are in generation, not in retrieval.
- **Reranking is half the cost of an answer.** It is also what took recall@1 from 82% to 91-95%; if cost has to go down, it is the first stage to measure with a cheaper model (#47).


## Iterations: what each measurement decided

Chronological. Each row is a change that was measured before it was kept or deleted.

| Date | Change | Measured | Decision |
|---|---|---|---|
| 2026-09-20 | Chunking by article vs fixed size (1,000 chars, 200 overlap) | 47% of fixed-size chunks span two articles and cannot be cited; by article, none | Chunk by article ([ADR 0009](decisions/0009-chunking-strategy.md)) |
| 2026-09-20 | Retrieval threshold | 29 questions: in-domain and out-of-domain score ranges | 0.5 for the small model ([ADR 0012](decisions/0012-retrieval-baseline-and-tuning.md)) |
| 2026-09-21 | Hybrid search (full-text + vectors, RRF) | recall@1 82% → 77% | **Deleted** ([ADR 0013](decisions/0013-advanced-retrieval-measured.md)) |
| 2026-09-21 | Query reformulation | recall up, out-of-domain refusals 86% → 57% | **Deleted** ([ADR 0013](decisions/0013-advanced-retrieval-measured.md)) |
| 2026-09-21 | Reranking, pool of 20 | recall@1 82% → 91%, refusals intact; pool of 10: no gain | Kept ([ADR 0013](decisions/0013-advanced-retrieval-measured.md)) |
| 2026-09-21 | Q&A prompt v2 (opening must survive the answer) | The #34 answer no longer contradicts itself (by hand) | Kept; now a regression case |
| 2026-09-21 | Grounding check, all-or-nothing | Refused 23% of correct answers | **Replaced** by a 0.7 threshold: answered 91%, out-of-domain refused 100% ([ADR 0014](decisions/0014-grounding-and-retrieval-security.md)) |
| 2026-09-24 | `text-embedding-3-large` at 1,536 dims, threshold 0.40 | End to end: answered 82% → 91%, cites expected 77% → 86%, refusals 100% | Kept ([ADR 0015](decisions/0015-embedding-model-measured.md)) |
| 2026-09-24 | Semantic cache for reviews | A changed illegal clause scores 0.966–0.996; a rewording 0.912–0.982 | **Not built** ([ADR 0019](decisions/0019-no-semantic-cache.md)) |
| 2026-09-25 | First answer evaluation, Q&A prompt v1 vs v2 | v2: answered 84% → 92%, cites expected 76% → 88%, correctness 0.68 → 0.76; the #34 regression case **fails on both** | Keep v2; the #34 fix is incomplete, a v3 is measured next ([ADR 0022](decisions/0022-answer-evaluation.md)) |

## How to run

```bash
docker compose up -d db && make migrate ingest      # the corpus, once
make benchmark-retrieval                             # ~$0.30 with the reranker
make eval-answers                                    # both variants, ~$1.20 and ~20 minutes
uv run python -m evals.answers.run --variant baseline   # one variant
```

Results go to `benchmarks/retrieval/results/` and `evals/results/` as JSON with every answer and every grade; they are not committed (they are reproducible, and large). The durable record of a measurement is its table here and in its decision record.

## Limitations

- **One run is one sample.** The generation, the reranker and the judge vary between runs; one question is 4 points on 25. Differences smaller than two questions are noise until #50 repeats runs and reports ranges.
- **32 questions** decide between techniques whose differences are large, not fine-tuning.
- **The judge is a model** on a different provider; its analysis is kept so its grades can be checked.
- **No online evaluation yet.** What real users ask and find wrong arrives with the feedback of #51.
