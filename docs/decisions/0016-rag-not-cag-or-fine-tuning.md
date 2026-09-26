# 0016. Why the regulations are retrieved, not put in the prompt or trained into a model

- **Status**: Accepted
- **Date**: 2026-09-24
- **Issue**: #56

## Context

The project uses both architectures the course starts with. The listing review is CAG: a five-point checklist, each point with its article, travels in every prompt ([ADR 0002](0002-prompt-strategy-and-checklist.md)). The regulation Q&A is RAG. That split was decided early and never argued with numbers, and the obvious question has an uncomfortable answer: **the whole corpus would almost fit in the context window**. The session on data-driven AI lists the conditions under which CAG is enough and the reasons to prefer RAG over fine-tuning; this record checks the corpus against both.

## CAG with the whole corpus: the four conditions

The session's rule is that CAG works only if all four hold. Measured with Anthropic's token counter, the 380 chunks as the model would read them (numbered, with law and article) are **187,883 tokens**.

| Condition | This corpus | Holds? |
|---|---|---|
| The corpus fits in the window | 187,883 of Claude Haiku 4.5's 200,000: **94%**, before the system prompt, the question and the answer. The session's working limit is 50-70% | **No** |
| The cost per call is acceptable | $0.188 of input per question at $1 per million, against **$0.016** measured end to end with RAG ([ADR 0015](0015-embedding-model-measured.md)): ~12x. Provider prompt caching would cut reads to ~$0.019, but every cache write costs 1.25x ($0.235) and the cache lives 5 minutes, so at this traffic most questions pay the write. A fallback to OpenAI shares no cache at all | No |
| The latency is acceptable | 188k input tokens per question, against ~13k with RAG | No |
| The model uses the whole context | Lost in the middle: a 380-article context puts almost every article in the middle | Doubtful |

It fails on the first one. And the corpus is four laws: the Catalan housing law alone is half of it, so adding one more region would put it over any window on offer.

Two things RAG gives here that CAG cannot, measured:

- **A refusal that costs nothing.** When no article clears the threshold, the question is refused without calling a model: 0 tokens, 0.9 s ([ADR 0011](0011-grounded-answers-and-citations.md)). With the corpus in the prompt, "¿Qué tiempo hará mañana en Bilbao?" costs $0.19.
- **A small context to verify against.** The grounding judge reads only the cited articles ([ADR 0014](0014-grounding-and-retrieval-security.md)): ~0.8 s and $0.001.

Two arguments often made for RAG that are **not** decisive here, and are left out on purpose: citations (the numbered-fragment mechanism would work over a full numbered corpus too) and freshness (re-rendering a prompt is as cheap as re-embedding a changed article).

## Fine-tuning

The session's mentor reports needing it in none of his projects, and this one is no exception:

- **There is nothing to train on.** Fine-tuning needs question and answer pairs by the thousand; the project has 29 golden questions, written to evaluate, not to train.
- **The law changes.** The weekly drift check exists because the BOE amends these texts a few times a year. RAG re-embeds the changed articles for fractions of a cent; a fine-tuned model would need retraining with everything, every time.
- **A fine-tuned model cannot cite.** It does not know where a fact came from, so a citation it writes is a plausible invention. The whole point of this assistant is an answer someone can check against the BOE.
- **Cost and dependency**: training runs, a model tied to one provider's fine-tuning offer, and the provider fallback of [ADR 0005](0005-provider-fallback-cost-and-observability.md) would stop being possible.

## Decision

- **The regulations are retrieved.** RAG over the BOE corpus, as built in #2.
- **The checklist stays in the prompt.** Five points and their articles are a thousand tokens, stable, and needed in every review: that is the case CAG exists for, and retrieving them per review would add latency and a failure mode for nothing.
- **No fine-tuning.** It would become worth measuring only for a narrow, stable task with thousands of curated examples, such as classifying a listing's defects, and never for the knowledge of the law itself.

## Consequences

- The hybrid is the architecture, not a phase: CAG for what is always true, RAG for what has to be looked up, and the agent of #3 is where both meet in one review.
- The corpus can grow to other regions without a redesign: the only limits are the retrieval quality, which the benchmark measures, and the index, which [ADR 0015](0015-embedding-model-measured.md) says when to tune.
