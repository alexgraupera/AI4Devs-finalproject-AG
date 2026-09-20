# 0003. The review output schema

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #8 (part of #1)

## Context

The answer has to be rendered in a UI, measured by the evals and, later, fed to an agent. Free text cannot do any of that reliably.

## Options considered

- Free text, parsed afterwards.
- JSON described in the prompt and parsed by hand.
- A Pydantic schema the model must fill, validated on arrival and re-prompted when it does not fit.

## Decision

- **`ListingReview` is the contract**: a list of `Finding` plus a `verdict` and a `summary`. Instructor sends the schema to the model and validates the answer against it, re-prompting up to `LLM_MAX_RETRIES` times.
- **Field order is part of the prompt**: `findings` first, then `verdict`, then `summary`. The model commits to the evidence before it commits to the conclusion, instead of writing a verdict and justifying it afterwards.
- **`severity` is an enum, not a number**: three levels the UI can render and the evals can count. `high` means it breaks the law or blocks publication.
- **`legal_basis` is optional**: quality findings have no article behind them, and forcing one would invite invention.
- **The verdict is derivable but explicit**: `request_changes` when any finding is `high`. Keeping it in the schema lets the evals check the model's own consistency, which is a signal worth measuring.

## Consequences

- The UI, the evals and any future agent share one contract; changing it is a versioned decision, not an accident.
- An invalid answer costs extra tokens (the re-prompt) instead of reaching the user broken.
- Categories are a closed enum: a new kind of finding is a code change, on purpose, so the evals can track categories over time.
