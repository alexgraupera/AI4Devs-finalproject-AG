# 0007. Exact-match cache

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #12 (part of #1)

## Context

The same listing gets reviewed more than once: the person edits a detail and asks again, a colleague pastes the same text, a demo runs the same example. Each of those costs a call to the model and about six seconds of waiting, for an answer that is already known.

## Decision

**Key on the prompts, not on the listing.** The cache key is a SHA-256 of the full system and user prompts plus the model and the prompt version. Keying on the listing text would have been the obvious choice and would have been wrong: editing the checklist, bumping the prompt version or switching the model would keep serving reviews produced by the old configuration. With the prompts in the key, any change that would have altered the answer changes the key by construction, so there is no cache to flush and no question of whether someone remembered to.

**A cache hit says so.** The response carries `cached: true` and the usage reports zero tokens and zero cost, with `provider: "cache"`. Reporting the original cost again would double-count spending in the dashboard; reporting nothing would hide that the answer is not fresh.

**The cache never breaks a review.** A Redis failure is logged and treated as a miss, on both read and write. The cache is an optimisation; making it a dependency would mean one more thing that can take the product down.

**Without Redis, the system runs.** An empty `REDIS_URL` wires a null cache, so local runs and the tests need no infrastructure. Docker Compose sets the URL and keeps Redis internal, with no published port: the cache is not an interface.

**Not everything is stored.** A text the model rejects as "not a listing" is not cached: it is cheap to recompute and unlikely to be sent twice, and caching negatives invites serving a stale refusal after a prompt change.

**TTL of 24 hours by default.** Long enough for the edit-and-retry loop that motivates the cache, short enough that a review never long outlives the corpus and the criteria that produced it.

## Consequences

- Measured on a repeated review: **5,672 ms and 0.0055 USD** the first time, **1 ms and 0 USD** the second. That is the whole point of the CAG layer.
- Hit rate depends on people repeating exactly the same text and fields. The semantic cache (#14) covers the near-misses: same flat, different wording.
- Reviews live in Redis. They contain the listing's findings, not the listing itself, and no personal data reaches the cache because the input guardrail rejects it first.
- One more service in the compose file, and one more thing to provision when deploying (#5). The null cache keeps that from being a blocker.
