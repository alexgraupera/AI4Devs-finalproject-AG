# 0033. Observability as structured events, the agent's trace and a request id, without a tracing platform

- **Status**: Accepted
- **Date**: 2026-09-26
- **Issue**: #55 (part of #5)

## Context

The course points at tracing platforms (Langfuse, LangSmith) as the way to see what an LLM application does in production: every call, its prompt, its output, its cost, grouped by session. This project records what it does from the first issue ([ADR 0005](0005-provider-fallback-cost-and-observability.md)), but never adopted one. That was a decision, and the evaluation asks for the reasons.

## Decision

**No tracing platform. Observability is three things the service already produces:**

1. **Structured events** (`structlog`, JSON in production), one per thing worth counting, never with the text of a listing or a question:

   | Area | Events |
   |---|---|
   | Model calls | `listing_review.completed`, `regulations_qa.completed`, `rerank.completed`, `llm.truncated`, `llm.model_not_in_pricing_table`: provider, model that answered, tokens, attempts, latency, cost, prompt version |
   | Quality signals | `regulations_qa.invented_citation`, `regulations_qa.grounding_failed`, `regulations_qa.no_context`, `guardrail.dropped_finding`, `agent_review.invented_source`, `agent_review.rewrite_new_figures`, `agent.critic_unverified_rejection` |
   | Agent | `agent_review.completed` / `agent_review.paused` (steps, tools called, fragments read, stop reason, escalation, cost), `agent_review.critic`, `agent_review.human_decision`, `agent.tool_failed`, `agent.forced_submission` |
   | Security and money | `guardrail.rejected`, `security.rejected`, `rate_limit.exceeded`, `spend.cap_reached`, `agent.audit` (every tool call, allowed or denied, arguments masked) |
   | People | `feedback.recorded`, linking a vote to the request it rates |

2. **The agent's trace, returned with the review**: every step with its tool, arguments, result, latency and the model's reasoning, plus the cost broken down by step ([ADR 0031](0031-agent-vs-pipeline.md)). The person who reads the review sees how it was made; nothing has to be looked up elsewhere.

3. **A `request_id` bound to every event of a request** and returned in its response (#51), and a `run_id` bound to every event of an agent run. A thumbs down leads to the request, the request to its events, and the events to the prompt version, the model and the articles read.

### Why not Langfuse or LangSmith

- **They would receive the listings.** A trace worth having holds the prompt, and the prompt holds the listing's text: personal data, sent to one more processor. The service keeps no listing ([ADR 0018](0018-data-privacy-and-providers.md)); a tracing platform would be the place where every listing is kept.
- **The questions they answer are already answered.** What each model costs, which prompt version is live, when the fallback fires, how often a citation is invented, which step of the agent costs most: the events and the trace answer each of these, and the evaluation runners ([`docs/evals.md`](../evals.md)) are where quality is measured, with datasets that live in the repository.
- **The volume does not need it.** A demo with a handful of requests a day is read in the logs; a platform is one more service to run, secure and pay for, on a deployment whose infrastructure cost is zero ([ADR 0021](0021-hosting-on-render.md)).

## Consequences

- There is no UI to browse traces: the logs are searched by `request_id` or `run_id`, and the agent's trace is in the response and in the page.
- There are no sessions or replays: a review is one request, and a paused one is one run, so there is nothing longer to group.
- **What would change the decision**: real traffic with several people debugging it, a need to compare prompt versions on live traffic, or a multi-turn flow. Then a self-hosted Langfuse (open source, in the EU), fed with the same events through OpenTelemetry and the listing's text masked before it leaves the service, the same way the feedback comment is masked today.
