# 0020. Access, spend and probes for a public deployment

- **Status**: Accepted
- **Date**: 2026-09-24
- **Issue**: #53 (part of #5)

## Context

The deployment of #54 puts the API on the internet: the free hosting tier cannot receive private traffic, so the API is public even though only the UI should call it. Before that, the service had one guard, on the regulations router, and the listing review (the most-called endpoint, a model call every time) was open. Nothing capped what a day could cost, a missing secret was a warning, and `/health` checked the database, which is the probe a platform uses to decide whether to restart the process.

The production session lists these exact failures: an empty token that compares equal on both sides, a liveness probe that kills a busy but healthy service, cost-exhaustion attacks ("denial of wallet"), and published database ports that bypass the host firewall.

## Decision

### Two access layers, so exposure needs two mistakes

- **Service token** (`X-Service-Token`), a middleware over the whole app: may you talk to this service at all. Only the UI holds it here; in a marketplace, only the business backend would.
- **API key** (`X-API-Key`) and **rate limit**, as dependencies of **every business router**, listings included: which endpoints you may use, and how often.

Both compare in constant time and answer a missing secret and a wrong one with the same 401. The probes and the OpenAPI docs are outside both: a probe that needs a secret stops working the day the secret rotates, and the contract is not a secret.

`RAG_API_KEY` becomes `API_KEY`, since it now guards everything. The old name is still read so an existing `.env` keeps working.

### Fail fast in production

With `ENVIRONMENT=production`, the app refuses to start if the API key, the service token, either provider key, `DATABASE_URL` or `REDIS_URL` is empty, naming the missing settings and never a value. An empty token does not fail later: it compares equal to the empty header of any caller and opens the door, silently. Development keeps starting with everything empty, with a warning on every request.

### A daily spend cap that stops, not one that alerts

The rate limiter bounds one caller; it does not bound what all callers spend together. A Redis counter of today's cost (UTC) is checked **before** every model call and incremented with the real cost after it. At `DAILY_SPEND_CAP_USD` (default **$2**, about 120 regulation answers or 350 reviews) the service answers `503 budget_exhausted` with `Retry-After` until midnight. It stops rather than alerts because nobody may be watching when a loop, or somebody else's script, starts spending. The provider's own limit stays as the last line: when that one trips, every feature stops at once and nobody chose which.

Two details that matter: a **cache hit is served even when the budget is spent**, because it costs nothing; and a model **missing from the price table** is logged, not counted as free, because counting it as zero would let an unpriced model spend without limit.

Like the rate limiter and the cache, the guard **fails open** when Redis is down, and says so in the logs.

### Liveness is not readiness

- **`/health`**: is the process alive? No I/O at all. The platform restarts on failure, so it must fail only when a restart helps.
- **`/ready`**: can it take a request now? The corpus store, the cache and today's budget, with `503` and `Retry-After` when the answer is no. A service out of budget or waiting for its database needs traffic sent elsewhere, not a restart that loses the reviews in flight.

The cache being down is reported by `/ready` but does not make the service unready, since everything behind it fails open.

### Smaller things from the same session

- **Rejected inputs are logged** (`guardrail.rejected`, the reason and the text length, never the text): a burst of `prompt_injection` from one caller is a signal worth counting.
- **The container entrypoint** migrates, then `exec`s the server, so the server is PID 1 and receives the platform's SIGTERM.
- **Compose publishes every port on the loopback only**: `5432:5432` publishes Postgres on every interface, and Docker's rules bypass a host firewall such as UFW.
- **The phone pattern of the PII layer** missed "612 345 678", the usual way to write a Spanish mobile. It now matches nine digits starting with 6-9 however they are grouped.

## Consequences

- Behind the UI, every visitor shares the UI's API key, so the rate limit is effectively global for the public demo: 30 requests a minute across all visitors. For a demo that is the right shape (the spend cap is the real bound); per-visitor limits would need the UI to forward a visitor identity the API trusts because the token vouches for the UI.
- The spend cap counts the model calls the conductors make. When a later step fails after an earlier one was paid (the reranker ran, the answer did not), that earlier cost is not recorded: the counter errs low by at most one call.
- A second instance of the API shares the rate limit and the budget through Redis. Nothing in the service keeps state in memory that a load balancer would split.
