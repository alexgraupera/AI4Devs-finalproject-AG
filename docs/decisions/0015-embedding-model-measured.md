# 0015. The embedding model, measured, and why the index is not tuned

- **Status**: Accepted (supersedes the model and threshold of ADR 0010)
- **Date**: 2026-09-24
- **Issue**: #56

## Context

[ADR 0010](0010-embedding-model-and-index.md) chose `text-embedding-3-small` because switching later is one command, and left the comparison to the benchmark of #24. The benchmark was built and used for everything except that comparison. [Migration 0002](../../migrations/versions/0002_chunk_embeddings.py) did the same with the index: HNSW at pgvector's defaults, "revisit with the retrieval benchmark of #24". Nobody came back to either.

The session on embeddings asks for at least two models compared on your own labelled set; the session on vector databases asks for exact vs approximate recall and an `ef_search` sweep. This record does the first and explains, with evidence, why the second does not apply yet.

## The comparison

`text-embedding-3-large` supports shortening its vectors (Matryoshka), so it was measured at **1,536 dimensions**, the size the typed column already has: the switch needs no migration.

**A threshold belongs to a model.** The large model scores everything lower. At the small model's 0.5, two answerable paraphrases retrieved nothing at all. Comparing the models at the same threshold would have measured the threshold, so the large model's was swept first:

| `text-embedding-3-large` | recall@1 | recall@3 | MRR | out-of-domain with nothing retrieved |
|---|---:|---:|---:|---:|
| threshold 0.35 | 86% | 100% | 0.932 | 71% (weather and home insurance leak) |
| **threshold 0.40** | **86%** | **100%** | **0.932** | **86%** (home insurance leaks, 0.447) |
| threshold 0.45 | 86% | 95% | 0.909 | 100% |
| threshold 0.50 | 82% | 91% | 0.864 | 100% |

0.40 keeps every answerable article in the top three and lets through exactly the question the small model already let through ("¿Cuánto cuesta el seguro de hogar?"). [ADR 0012](0012-retrieval-baseline-and-tuning.md) accepted that leak because the generation refuses it, and [ADR 0014](0014-grounding-and-retrieval-security.md) closed it from the other side. A leak the next layer closes is recoverable; an article that was never retrieved is not.

Retrieval benchmark, both models at their own threshold, same day:

| | recall@1 | recall@3 | MRR | out-of-domain with nothing retrieved |
|---|---:|---:|---:|---:|
| small @ 0.50, dense | 82% | 95% | 0.871 | 86% |
| **large @ 0.40, dense** | **86%** | **100%** | **0.932** | 86% |
| small @ 0.50, rerank 20 | 86% | 100% | 0.924 | 86% |
| **large @ 0.40, rerank 20** | **95%** | **100%** | **0.977** | 86% |

And end to end, the 29 golden questions through the real `RegulationQAService` (rerank, answer, grounding check), same day, same models:

| | small @ 0.50 | **large @ 0.40** |
|---|---:|---:|
| Answerable questions answered | 82% (18/22) | **91% (20/22)** |
| Answer cites the expected article | 77% (17/22) | **86% (19/22)** |
| Out-of-domain questions refused | 100% (7/7) | 100% (7/7) |
| Cost per question | $0.0150 | $0.0162 |
| Latency p50 / p95 | 8.7 s / 15.7 s | 8.7 s / 16.7 s |

## Decision

**`text-embedding-3-large` at 1,536 dimensions, with `RETRIEVAL_MIN_SCORE=0.40`.**

The gain is two questions out of 22 end to end, and the README of the benchmark warns that one question is 4.5 points. What makes it a decision rather than noise is that **every metric moves the same way in both benchmarks and none gets worse**: recall, MRR, answers, citations, with the refusals intact. Against that, the cost is a reindex of $0.0201 instead of $0.0031 and 8% more per question, mostly because more questions now get answered, and answering costs more than refusing.

OpenAI's multilingual benchmark (MIRACL) already favoured the large model for a Spanish corpus; now this corpus agrees.

## Why the index is not tuned

`EXPLAIN ANALYZE` of the real query over the 380 chunks:

```
Sort  (top-N heapsort)
  ->  Hash Join
        ->  Seq Scan on chunks c   (rows=344)
Execution Time: 4.437 ms
```

The planner does not use the HNSW index at all: at 380 rows a sequential scan is cheaper, so **every search today is exact**, with 100% recall by definition and 4.4 ms in the database. The query spends ~250 ms on the embedding call and ~4 ms on the search.

That settles the checks of the vector database session for now:

- **Exact vs HNSW recall**: nothing to measure; there is no approximation in the path.
- **`ef_search` sweep**: it would tune an index the planner does not read.
- **`halfvec`**: the vectors take 2.3 MB and the index 6 MB.

The index stays, because it costs nothing and is there when the planner wants it. What would make this worth revisiting, and what to do then:

- **Around 10,000 chunks** (several regional laws), the planner switches to HNSW. Then: exact vs HNSW recall on the golden set, and an `ef_search` sweep for the latency/recall elbow.
- **Filtered queries on HNSW** can return fewer than `k` rows. pgvector 0.8.6 (the version in use) has iterative scans (`hnsw.iterative_scan`) for that; turn them on when the index starts being used with jurisdiction filters.

## Consequences

- `EMBEDDING_MODEL=openai/text-embedding-3-large` and `RETRIEVAL_MIN_SCORE=0.40` are the defaults. An existing corpus picks the model up with `make embed`, which re-embeds only the rows whose model differs.
- Any other model, or other dimensions, needs its threshold swept again: the benchmark's `RetrievalVariant` takes the threshold as a parameter for exactly that.
- The comparison is one run per configuration. The reranker is a model and varies between runs (its recall@1 with the small model was 91% in ADR 0013 and 86% here); the evaluation suite of #4 repeats runs and reports ranges.
