# 0013. Advanced retrieval: what was measured, and what was deleted

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #25 (part of #2)

## Context

The benchmark of #24 said every retrieval failure was a paraphrase, and not one legal-wording question missed. Three techniques were built to attack that, each with an explicit hypothesis, and each measured against the same golden set through the same harness.

**Two of the three hypotheses were wrong.** That is the reason this phase existed.

## What was measured

All variants over 29 questions, `k=5`, threshold 0.5, same corpus, same embedding model:

| Variant | recall@1 | recall@3 | recall@5 | MRR | no-answer | p50 |
|---|---:|---:|---:|---:|---:|---:|
| **`dense`** (baseline) | 82% | 95% | 95% | 0.871 | **86%** | 226 ms |
| `dense+reform` | 82% | 95% | 100% | 0.890 | **57%** | 1,168 ms |
| `hybrid` | **77%** | 95% | 95% | **0.848** | 86% | 236 ms |
| `hybrid-open` | 77% | 95% | 95% | 0.848 | 86% | 235 ms |
| `hybrid+reform` | **68%** | 95% | 100% | **0.807** | **29%** | 1,167 ms |
| `dense+rerank` (pool 10) | 82% | 95% | 95% | 0.886 | 86% | 1,936 ms |
| **`dense+rerank` (pool 20)** | **91%** | **100%** | **100%** | **0.955** | **86%** | 2,403 ms |

## Hybrid search: built, measured, deleted

**The hypothesis**: legal questions carry rare proper nouns ("Basauri", "cédula de habitabilidad") and a dense vector averages them away, which is exactly where PostgreSQL full-text search wins.

The lexical index worked as expected in isolation: `websearch_to_tsquery('spanish', 'Basauri zona tensionada')` matches exactly one chunk in 380, the right one.

**The measurement said no anyway**: recall@1 fell from 82% to 77% and MRR from 0.871 to 0.848, with no improvement in refusals. Letting lexical hits bypass the similarity threshold (`hybrid-open`) changed *nothing at all*, which is the clue: on a corpus of 380 homogeneous legal articles, common legal vocabulary matches everywhere, so fusion injects noise faster than it adds the rare match. The RRF fusion then promotes chunks that are lexically plausible and semantically wrong.

**Deleted**: the `0003_chunk_fulltext` migration, the `tsvector` column, the GIN index, the fusion code and the strategy switch. It would become interesting on a corpus large and varied enough that lexical noise is not the dominant term.

## Query reformulation: built, measured, deleted

**The hypothesis**: rewriting "¿me pueden pedir dos meses de fianza?" into "prestación de fianza en metálico, cuantía" closes the gap the benchmark identified.

**It half worked, and broke something more important.** Recall@5 reached 100% and MRR moved from 0.871 to 0.890, but the **no-answer rate collapsed from 86% to 57%**. The rewrite is the problem it solves: turning a question into legal-sounding vocabulary works just as well on "¿Cómo se cambia una rueda del coche?", which then matches an article above the threshold. Out-of-domain leaks went from 1 in 7 to 3 in 7, and with reranking on top, to 4 in 7.

This is the same trade ADR 0012 refused when tuning the threshold, and it is refused again for the same reason: on a compliance assistant, answering something that should have been refused is worse than ranking the right article second.

**Deleted**: `reformulation.py` and the `regulations_query` prompts. The prompt design is preserved in this record, and the technique is worth revisiting with a guard that detects when the rewrite has drifted off-domain.

## Reranking: kept, with its pool size

**The hypothesis was the most pessimistic of the three**: chunks are whole articles, so the candidates are already coarse and there may be little left to reorder.

**It is the only technique that paid.** recall@1 82% → 91%, recall@3 95% → 100%, MRR 0.871 → 0.955, and **the refusal rate did not move**. Per question: four improved, one worsened, seventeen unchanged. The flagship failure of ADR 0012, "¿Necesito algún papel que diga que el piso es habitable...?", went from **not retrieved at all** to rank 1.

**The pool size is the whole trick.** With 10 candidates instead of 20, the gain disappears entirely (recall@1 stays at 82%): the missing article is not in the pool, so there is nothing to rescue. Reranking works here not by polishing an order but by letting retrieval go wide and having a model that reads the articles do the choosing. It is `CANDIDATE_POOL = 20` and `RETRIEVAL_TOP_K = 5`, and the first number matters more than the second.

**Cost**: about 7,000 input tokens and 2.4 s per question, which roughly doubles the cost of an answer (~$0.005 → ~$0.013) and takes it from ~2 s to ~5 s. For a corpus whose whole purpose is citing the right article, paying a cent to not miss it is the right trade. `RERANK_ENABLED=false` turns it off.

## Two defects the measurement did not catch

**The context builder was undoing the reranker.** `build_context` re-sorted the fragments by similarity score, which silently threw away exactly the ordering the reranker had just produced. The benchmark could never have caught this: it measures what the retriever returns, not what reaches the model. A unit test did. `build_context` now keeps the order it is given, and says so: ordering is the caller's job.

**The reported cost excluded the reranker.** The usage of the reranking call was logged but not added to the answer's usage, so every answer under-reported its cost by about two thirds. Both calls are now summed, because a service that claims to report what it spent has to report all of it.

## Consequences

- One technique of three survives. The other two are gone from the code, not disabled: a flag nobody sets is a maintenance cost plus a lie in the configuration.
- The measured recall@1 of the system is **91%**, with the right article in the top three for **every** answerable question in the set.
- Answers now cost ~$0.013 and ~5 s. That is the price of the 9 points of recall@1, stated so it can be reconsidered.
- 29 questions remain a small set: the +9 points is four questions moving, three of which were the known paraphrase failures. The direction is consistent and the refusal rate is untouched, which is what makes it believable; the exact number is not.
- Hybrid search and reformulation are documented here with their numbers, so neither gets re-proposed from intuition.
