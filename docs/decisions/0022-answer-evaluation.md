# 0022. Evaluating the answers: RAGAS-style metrics on a judge we own

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #48 (part of #4)

## Context

Until now the project measured what reaches the model (the retrieval benchmark of [ADR 0012](0012-retrieval-baseline-and-tuning.md)) and, once, by hand, what the grounding check did to the answers ([ADR 0014](0014-grounding-and-retrieval-security.md)). Nothing measured, repeatably, whether an answer is faithful to the articles, answers the question and says what the law says. The session on RAG evaluation asks for exactly that: context recall and precision on the retrieval axis, faithfulness and answer relevance on the generation axis, on a golden set with realistic, vague and out-of-domain questions, a baseline, and a regression case.

## Decision

**One command, `make eval-answers`, runs the golden questions through the real `RegulationQAService`** (guardrails, retrieval, reranking, generation, citation checks, grounding) and a judge grades what comes back. The same questions under named configurations are an A/B.

**The metrics are RAGAS-style, computed without the `ragas` library:**

- The **retrieval axis comes from the labels**, exact and free: whether an expected article reached the context (context recall) and whether the answer cites it (citation accuracy). Context precision is left out on purpose: it needs every retrieved chunk labelled relevant or not, and the golden set labels only the articles that answer the question. Labelling ~150 chunks by hand for one metric is not worth it at this size.
- The **generation axis comes from a judge**: faithfulness (share of the answer's legal claims the context supports), relevance, correctness against a reference answer, and whether the opening survives the rest of the answer (the bug of #34).

Why not the library: it would add a dependency tree larger than the service's, bring its own prompts and its own model client, and grade with rubrics we cannot read in this repository. Here the judge goes through the same wrapper as the service (fallback, retries, cost accounting), its prompt is versioned next to the others, and the rubric is a file anyone can review.

**The judge reads, code counts.** The model lists the claims and marks each supported or not, and grades relevance and correctness on three levels (`yes`, `partly`, `no`) with examples in the rubric. Faithfulness is the share of supported claims, computed in code; the grades map to 1, 0.5 and 0 in code. A model asked for "a faithfulness between 0 and 1" returns a plausible decimal, not a measurement.

**The judge runs on the other provider** (GPT-5.4 mini, falling back to Haiku), so it does not share the blind spots of the model that wrote the answer.

**Every answerable question has a reference answer** written from the text of the expected article as ingested, not from memory, and a test fails if one is missing.

**The evaluation bypasses caches and the spend guard**: an evaluation that reads a cache measures the cache.

**Cost is attributed per stage.** A recording wrapper between the service and the model names every call by the schema it asked for, so the report splits the cost of an answer into rerank, generation and grounding without the service knowing it is being measured.

## The golden set grows

29 → **32 questions**, one file for retrieval and answers (a second file would drift from the first):

- two where the **state and Catalan rules differ** ("¿Hace falta cédula de habitabilidad para alquilar un piso?"), which the answer must keep apart;
- the **regression case of #34** ("Mi casero me pide 3 meses de fianza, ¿puede?"), which passes only if the answer cites article 36 and its opening holds. The `prompt-v1` variant keeps the prompt before the fix, so the case has a configuration it should fail on: a regression case that has never been seen failing has not been shown to catch anything.

## Consequences

- A full run of one variant costs about $0.60 and ten minutes; both variants, about $1.20. That is cheap enough to run before any prompt or model change, and too slow and non-deterministic for every pull request: #50 puts it on a schedule with a gate.
- One run is one sample. The generation, the reranker and the judge all vary between runs, so differences of one or two questions (4-8 points on 25) are noise until #50 repeats runs and reports ranges.
- The judge has its own errors: it is a model. [ADR 0014](0014-grounding-and-retrieval-security.md) found the grounding judge wrong in both directions; this one is on a different model and provider, and its analysis is kept with every grade so a doubtful grade can be read and checked.
