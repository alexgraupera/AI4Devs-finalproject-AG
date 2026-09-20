# Retrieval benchmark

What this answers: **did that change to the retrieval actually help?**

```bash
DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental make benchmark-retrieval
```

It needs the corpus ingested and embedded (`make ingest`). It costs the embedding of 29
questions per variant, about **$0.00001** per full run.

## What is measured

| Metric | What it catches |
|---|---|
| `recall@k` | The right article was somewhere in the results. This is the ceiling on what the answer can possibly cite: an article that was never retrieved cannot be cited. |
| `MRR` | How high the right article landed. Recall says "somewhere in the five"; MRR says whether it was first or fifth. |
| `no-answer rate` | Over the out-of-domain questions, how often the retrieval correctly returns nothing. Without it, any change that retrieves more would look like an improvement. |

Out-of-domain questions are excluded from recall and MRR: including them would let a retrieval
that returns nothing at all score 50%.

## The question set

`questions.yaml`, 29 questions in three families:

- **`legal-wording`** (10): phrased as the law phrases it. The floor.
- **`paraphrase`** (12): the wording a landlord actually uses. The interesting case.
- **`out-of-domain`** (7): nothing to find, including one near the domain and one prompt injection.

Questions are keyed by **law and block id**, never chunk id: chunk ids change on every
re-ingestion. `expected: []` means retrieving nothing is the correct answer.

Two questions point at RD 390/2021 articles 15 and 16 on purpose. They are near-identical
(the label in the advertisement, the label displayed in the building) and a retrieval that
confuses them should be visible, not averaged away.

## Reading the output

A Markdown table on stdout, plus a timestamped JSON under `results/` with the per-question
detail, so two runs can be diffed locally. Those files are **not committed** (100 KB each, and
reproducible in seconds): the durable record of a measurement is the table in its decision
record.

The table is followed by the questions whose right article did not land first, and the
out-of-domain questions that returned something anyway. Those two lists are where the next
improvement is.

**29 questions is small.** One question moving changes recall by three points, so treat
differences under ~7 points as noise. The set is sized to decide the questions of #25
(reformulation, hybrid search, reranking), which are not subtle.

## Adding a variant

Register it in `VARIANTS` in `run.py`. Every technique goes through the same harness, which is
what turns "hybrid search is better" into a row in a table.

## What this is not

It measures **what reaches the model**, not what the model does with it. Faithfulness, citation
accuracy and refusal quality are the evaluation suite of #4, which reuses this question set
rather than inventing another one.
