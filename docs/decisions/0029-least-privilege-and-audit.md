# 0029. Least privilege over the agent's tools, and an audit of every call

- **Status**: Accepted (scope reduced on 2026-09-24: audit as structured events, no table)
- **Date**: 2026-09-25
- **Issue**: #43 (part of #3)

## Context

The agent's tools were one list handed to one model call. The session on multi-agent systems asks for three containment layers: tools classified by who may use them, validation before execution, and an audit of everything, because with non-deterministic routing the logs are the only source of truth about who did what, and a burst of refused calls is what a prompt injection looks like.

## Decision

- **Roles and permissions as data** (`app/generation/agentic/policy.py`): the reviewer may call `check_listing_fields`, `search_regulations` and `submit_review`; the critic and the rewriter call nothing. **Deny by default**: a tool registered without being granted is refused, so adding a tool (publishing a listing, calling the Catastro) is a refusal until someone writes down who may use it.
- **The check sits in front of the executor, not in the prompt.** A denied call never reaches the tool; the model reads "Llamada denegada: … no está permitida para este rol" and the run goes on. A rule that lives only in a system prompt is one a model can be talked out of. The model is also only *offered* the tools its role may call, and the check holds even when it asks for one it was never shown.
- **Every call is audited** as a structured `agent.audit` event: role, tool, outcome (`allowed`, `denied`, `failed`), latency and the run id. **Arguments are redacted**: a listing can carry personal data, so only the names, types and lengths of arguments are kept, plus the search query, the one worth reading back.
- **Argument validation** stays in each tool, which returns a readable error the model can correct (ADR 0024); the policy decides *whether* a call runs, the tool *how*.

### Why events and not a table

The plan had a Postgres table and an endpoint to read a run's audit. It was reduced on 2026-09-24, with the delivery twelve days away: the session asks for an audit of every call and every denial, and structured events already give that, with the run id to correlate them and the same pipeline as every other event of the service. A table earns its place when the audit has to be queried by people who do not read logs, and that is listed as a next step.

## Consequences

- Today only one role calls tools, so the table mostly says who may *not*. That is its value: it is written before the first tool with side effects arrives, not after.
- A spike of `denied` events from one run is the signal to alert on; the alert itself is not built.
- The audit is only as durable as the logs. On the free hosting tier they are the platform's logs, with its retention.
