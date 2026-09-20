# 0010. Embedding model, vector index and retrieval threshold

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #22 (part of #2)

## Context

380 chunks of Spanish legislation need vectors, an index to search them, and a threshold that decides when the corpus simply does not answer a question. Each of those three is a number someone has to defend.

## Decision

**`openai/text-embedding-3-small` at 1536 dimensions.** Measured on the real corpus: 154,287 tokens, **$0.0031** for a full reindex, 7.2 seconds. The larger model would cost $0.02 and score better on OpenAI's published multilingual benchmark (MIRACL, ~55% against ~44%), which matters for a Spanish corpus.

Cost is not what decided it, because at this size neither number is a constraint: the difference is under two cents per reindex. What decided it is that **the switch is cheap to make later**. `EMBEDDING_MODEL` is configuration, every vector stores the model that produced it, and `make embed` re-embeds whatever does not match. Starting with the smaller model and moving up if the benchmark of #24 shows it is worth it costs one command; starting with the larger one and discovering it was unnecessary costs nothing back. So the cheaper default is the reversible one.

A local model (multilingual-e5, bge-m3) was considered and rejected: it would add torch and sentence-transformers (~2 GB) to an image that today is small, and embedding on CPU takes minutes instead of seconds. It becomes interesting if the corpus ever cannot leave the machine, which is not this project's constraint.

**The model is stored per row, and the retrieval filters on it.** Two vector spaces in one index do not raise, they just return nonsense, which is the failure mode nobody notices. A chunk embedded with another model is invisible to the search until `make embed` refreshes it.

**HNSW with cosine distance, at pgvector's defaults (`m=16`, `ef_construction=64`).** With 380 rows every index is fast and a sequential scan would do; what HNSW buys is that it stays fast as regional laws are added, without a rebuild. Tuning the parameters at this corpus size would be measuring noise. IVFFlat was rejected for the opposite reason: it needs a representative sample to build its lists and wants rebuilding as the corpus grows, which is more operational surface for a corpus that changes a few times a year.

Cosine, not L2: the embeddings are normalised, so the two rank identically, and a cosine score maps to the 0–1 number a threshold can be read against.

**`RETRIEVAL_MIN_SCORE = 0.5`**, from the measured separation over 16 questions:

| | Range of the top score |
|---|---|
| 10 in-domain questions (deposit, expenses, energy label, Catalan offer, stressed areas, duration, rent updates, habitability certificate, non-payment) | **0.598 – 0.782** |
| 6 out-of-domain questions (weather, capital of France, a recipe, changing a tyre, football, a prompt-injection attempt) | **0.148 – 0.403** |

0.5 sits in the middle of that gap: 0.098 below the worst in-domain question and 0.097 above the best out-of-domain one. The previous default of 0.3 let "¿Qué tiempo hará mañana en Bilbao?" through at 0.403, which would have failed the acceptance criterion of #2 that out-of-domain questions are refused.

Sixteen questions is a sample, not a benchmark. This number is provisional and #24 re-measures it with the golden set and recall@k.

## Consequences

- A full reindex costs **$0.0031 and 7.2 s**; a routine one costs nothing, because only chunks whose text or model changed are embedded.
- A query costs one embedding call: **~250 ms end to end**, dominated by the provider round trip, not by the index.
- Changing the model is `EMBEDDING_MODEL` plus `make embed`. Changing the **dimensions** also needs a migration, because the vector column is typed: that is a deliberate trade, a typed column is what stops a 1536-dimension vector from being written next to a 3072-dimension one.
- The search endpoint ships one phase before the generated answer, so retrieval quality is inspectable with scores instead of being hidden behind a fluent paragraph. Two weaknesses are already visible: "¿Quién paga los gastos de gestión inmobiliaria?" ranks LAU art. 20 **second** (0.600) behind a Catalan article (0.602), and the energy-label question ranks art. 16 above the art. 15 the guide points at. Both are what query reformulation and hybrid search (#25) exist to fix, and what #24 will measure.
- The database-backed tests now run in CI against a pgvector service. They had been skipping silently, which is the worst kind of green.
