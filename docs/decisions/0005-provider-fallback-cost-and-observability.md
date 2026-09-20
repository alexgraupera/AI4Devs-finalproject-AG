# 0005. Provider fallback, cost and observability

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #10 (part of #1)

## Context

A review depends on a provider we do not control. Providers have outages, rate limits and price changes, and none of them is going to tell our users why the page is broken. On top of that, a system whose cost is invisible is a system nobody can decide about: the next phases (caches, retrieval, agents) are all trade-offs between quality, latency and money.

## Decision

**One logical model, two deployments.** The code asks the Router for `listing-reviewer` and never names a provider. The Router resolves it to Anthropic Claude Haiku 4.5, and falls back to OpenAI GPT-5.4 mini when the primary one fails. Which model answered is an output, not an input: it travels in `usage.model`, and it is how we know the fallback fired.

**Fallback is a different decision from retry.** `num_retries` covers a hiccup on the same deployment; the fallback edge covers the deployment being unusable. A per-request model override deliberately bypasses the Router and therefore has no fallback: if the caller pins a model, honouring it matters more than answering.

**Our own price table, looked up by longest matching prefix.** Providers answer with the snapshot they served (`claude-haiku-4-5-20251001`), while the table is keyed by the alias we ask for (`claude-haiku-4-5`). An exact lookup alone misses, and a missed lookup that returns zero would report every request as free. The longest prefix is load-bearing: `gpt-5.4-mini-…` starts with both `gpt-5.4` and `gpt-5.4-mini`, and the shorter one would over-price a mini call by more than three times. An unknown model returns **None**, not zero, and logs a warning: a gap is honest, a zero is a lie.

Prices come from the providers' public pricing pages, with the date recorded next to the table, because they change and a stale number is a wrong number.

**One structured event per review.** `listing_review.completed` carries prompt version, provider, model, tokens, latency, cost and whether the text was a listing at all. It is a JSON line, not a sentence, because the dashboard and the evals of #4 are built by counting these events, not by reading them.

**A documented limit**: when Instructor re-prompts after an invalid answer, the usage describes the final attempt, not the sum of the attempts, so a heavily retried call under-reports its cost. Stated in the code where the number is produced.

## Consequences

- An Anthropic outage degrades the answer to another model instead of breaking the product. Measured with an invalid primary key: OpenAI answered in 3.3 s, the client saw a normal review, and the log recorded the provider that served it.
- Two providers mean two bills and two spend limits to keep an eye on.
- The price table is maintenance: a model added in a later phase must be added here, or its calls report no cost.
- Cost per review is now a number we can compare: 0.0057 USD on Haiku 4.5 and 0.0030 USD on GPT-5.4 mini for the same listing, which is the kind of evidence #4 needs to choose a model on quality rather than on impressions.
