# 0012. Retrieval baseline, metrics and tuning

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #24 (part of #2)

## Context

Every retrieval decision so far rested on a handful of questions tried by hand. #22 set the similarity threshold from 16 questions and flagged it as provisional; #25 is supposed to keep hybrid search and reranking "only if they pay", which is not actionable without something to measure them with.

This phase adds no capability to the product. Its output is a number, and the ability to tell whether the next change was an improvement.

## Decision

**A golden set of 29 questions, in three deliberate families** (`benchmarks/retrieval/questions.yaml`):

- **`legal-wording` (10)**: the question phrased as the law phrases it. The easy case, and the floor: if these fail, nothing else matters.
- **`paraphrase` (12)**: the wording a landlord actually uses ("¿Me pueden pedir dos meses de fianza?" rather than "prestación de fianza en metálico"). This is the case reformulation and hybrid search are supposed to pay for.
- **`out-of-domain` (7)**: nothing to find, including one deliberately *near* the domain ("¿Cuánto cuesta el seguro de hogar?") and one prompt-injection attempt. Without these, any change that lowers the threshold would look like an improvement.

Questions are keyed by **law and block id**, not chunk id: chunk ids change on every re-ingestion, and a golden set that needs rewriting after every ingestion stops being golden. Two questions target the same pair of near-identical articles on purpose (RD 390/2021 art. 15, the label in the advertisement, and art. 16, the label displayed in the building), so a retrieval that confuses them is visible instead of averaging out.

**Three metrics, because each one hides a different failure.** `recall@k` says the right article was somewhere in the results, which is the ceiling on what the generation can possibly cite. `MRR` says how high it landed, which is what the context budget and the model's attention care about. `no_answer_rate` over the out-of-domain questions is what stops "retrieve more, retrieve looser" from looking free.

## The measured baseline

`dense-k5-t0.5`, over the 380-chunk corpus with `text-embedding-3-small`:

| Variant | k | threshold | recall@1 | recall@3 | recall@5 | MRR | no-answer | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`dense-k5-t0.5`** | 5 | 0.50 | **82%** | **95%** | **95%** | **0.871** | **86%** | 217 ms | 379 ms |
| `dense-k5-t0.3` | 5 | 0.30 | 82% | 95% | 95% | 0.871 | 71% | 224 ms | 267 ms |
| `dense-k5-t0.45` | 5 | 0.45 | 82% | 95% | 95% | 0.871 | 86% | 232 ms | 262 ms |
| `dense-k5-t0.55` | 5 | 0.55 | 73% | 86% | 86% | 0.780 | **100%** | 225 ms | 263 ms |
| `dense-k3-t0.5` | 3 | 0.50 | 82% | 95% | — | 0.871 | 86% | 229 ms | 331 ms |
| `dense-k10-t0.5` | 10 | 0.50 | 82% | 95% | 95% | 0.871 | 86% | 232 ms | 254 ms |

Cost per query: **$0.00000034** (the embedding of the question). The query side of retrieval is free in any practical sense; what costs money is the context it produces, measured in #23 at ~$0.005 per answer.

### By family

| Family | Right article first, or correctly empty |
|---|---|
| `legal-wording` | **10 / 10** |
| `paraphrase` | **8 / 12** |
| `out-of-domain` | **6 / 7** |

**All four failures are paraphrases.** Not one legal-wording question misses. The failure mode of this system is not retrieval quality in general: it is that the user's words are not the law's words.

| Question | Expected | Result |
|---|---|---|
| "¿Necesito algún papel que diga que el piso es habitable...?" | Ley 18/2007 art. 26 (cédula de habitabilidad) | **not retrieved at all** |
| "¿Qué me tienen que contar antes de firmar el alquiler?" | Ley 12/2023 art. 31 | rank 3 |
| "¿Hace falta el certificado energético para poner un anuncio?" | RD 390/2021 art. 15 | rank 3 |
| "¿Puedo subirle el alquiler a mi inquilino cada año?" | LAU art. 18 | rank 2 |

That is the case for query reformulation in #25, stated as a number instead of an intuition.

## Tuning decisions

**`RETRIEVAL_MIN_SCORE` stays at 0.5.** Raising it to 0.55 buys the last out-of-domain refusal (86% → 100%) and costs **nine points of recall** (95% → 86%). For a compliance assistant that is a bad trade: the one leak is "¿Cuánto cuesta el seguro de hogar?" at 0.5093, and #23 measured what happens to it — the generation refuses it anyway, for $0.002. Losing roughly one real answer in eleven to save two tenths of a cent is not a trade worth making. Lowering to 0.45 changes nothing measurable; lowering to 0.3, the value the plan originally assumed, costs 15 points of refusal rate for no recall gain.

**`RETRIEVAL_TOP_K` stays at 5**, and this one is less comfortable. Ranks 4 and 5 contributed **nothing** on this set: recall@3 equals recall@5 everywhere, so k=3 would give identical results with about 40% less context, which is where the real money is. It is not lowered because **this set cannot measure the case that would break**: every question has exactly one expected article, so a question needing both a state rule and a regional one — the situation the Q&A prompt has an explicit rule for — would look fine here and lose an article in production. Adding multi-article questions is the prerequisite for lowering k, and it is the first thing to do when this set is next extended.

## Consequences

- The defaults of #22 survive contact with a real measurement, and are now defensible rather than provisional.
- `make benchmark-retrieval` runs every variant and writes a timestamped JSON under `benchmarks/retrieval/results/` with the per-question detail. Those files are not committed: they are reproducible in seconds, and the table above is the record that lasts.
- **29 questions is a small set.** A single question moving changes recall by three points, so differences under ~7 points between variants should not be treated as real. That is the honest resolution of this instrument, and it is enough to decide the questions #25 asks, which are not subtle.
- The set is deliberately not an evaluation of the *answers*: it measures what reaches the model, not what the model does with it. Faithfulness, citation accuracy and refusal quality belong to #4, which reuses these questions rather than inventing another set.
- The metrics are hermetically tested; running the benchmark for real needs the corpus and costs a fraction of a cent.
