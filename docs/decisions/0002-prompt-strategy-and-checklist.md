# 0002. Prompt strategy and the review checklist

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #8 (part of #1)

## Context

The review must detect what a rental listing is missing and where it breaks Spanish rental law. That knowledge has to reach the model somehow: in the prompt, retrieved from a corpus, or hard-coded as rules.

## Options considered

- **Knowledge in the prompt (CAG-style context)**: a checklist written once, sent with every request.
- **Retrieval (RAG)**: search the regulations for every listing and build the context from the hits.
- **Deterministic rules**: code that inspects the listing text.

## Decision

- **The checklist lives in the system prompt**, versioned in `app/foundation/prompts/listing_review/v1/checklist.j2`. It is small (five legal points plus quality criteria), stable (the law does not change per request) and cheap: one stable block of context instead of a retrieval round trip per review.
- **Each checklist item carries the exact article that backs it**, and the prompt requires `legal_basis` to be copied verbatim from that list. A citation the model invents is worse than no citation, so the set of quotable sources is closed by construction.
- **Retrieval is for the Q&A over the regulations** (#2), where the question is open and the relevant article is unknown in advance.
- **Prompts are Jinja2 templates under a version directory**, rendered with `StrictUndefined`. Changing the prompt is a new directory and a string at the call site, so the diff between `v1` and `v2` is visible in the Git history and evals can compare versions.

## Consequences

- Every checklist item is auditable: it names the article it comes from, and we verified each one against the consolidated text in the BOE before writing it (see [`docs/data-sources/boe-legislation.md`](../data-sources/boe-legislation.md)).
- Growing the checklist grows the prompt of every request. The moment it stops being a short, stable list, it has to move to retrieval; the evals will show it as rising cost and falling precision.
- A template typo fails loudly instead of rendering an empty instruction the model would answer anyway.
