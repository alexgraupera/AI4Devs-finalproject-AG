# 0023. A model per role, and every call bounded

- **Status**: Accepted (the cross-provider measurement is scheduled for 2026-10-01, see below)
- **Date**: 2026-09-25
- **Issue**: #47 (part of #3)

## Context

Every model call went to one logical model: the review, the reranker, the answer and the grounding judge. The README listed the consequence as a limitation ("the judge that verifies is the same cheap model that writes"), and the course argues against it in four sessions: a model per task (S1, S9), strong where it pays and cheap where it does not (S2, S4), and a reviewer from another provider on the critical step (S13), because a judge that shares the writer's blind spots approves the writer's mistakes. No call had a timeout or a token budget either, and a truncated answer failed only by accident, when its half-JSON did not validate.

## Decision

**One router per role, each with its own fallback, built in the composition root.** The code that asks for a model never names one.

| Role | Primary | Fallback | Used by |
|---|---|---|---|
| Generator | Claude Haiku 4.5 | GPT-5.4 mini | Reviews, answers, the agent |
| Judge | **GPT-5.4 mini** | Claude Haiku 4.5 | The grounding check, the agent's critic (#40) |
| Reranker | the generator's | | Measured below |

**Every call is bounded**: a 45 s timeout, a 4,000-token budget, and temperature 0 (dropped for the reasoning models that reject it, instead of failing the call). A completion that stops on its token budget raises `ReviewGenerationError` and logs `llm.truncated`: a half-written structure never reaches a user, and it is not mistaken for "the model is bad" in the logs.

## What was measured

**The reranker stays on the generator's model.** Reranking is half the cost of an answer ([evals](../evals.md)), so the cheapest model that might keep the gain was tried, same day, same questions:

| Reranker | recall@1 | recall@3 | MRR | p50 |
|---|---:|---:|---:|---:|
| **Generator's model** | **92%** | 100% | **0.960** | 2.3 s |
| GPT-5.4 nano | 84% | 100% | 0.920 | 2.1 s |

Nano loses two questions of 25 at rank one, for about $0.003 saved per answer. The reranker exists to move the right article to the top; a cheaper one that moves it less is not a saving.

**The judge on the other provider could not be measured yet, and why is itself a result.** On 2026-09-25 the Anthropic account reached its monthly spend limit, and every Anthropic call started returning `invalid_request_error: You have reached your specified API usage limits` until 2026-10-01. The router fell back to OpenAI on every call, so in the run meant to compare "judge on GPT-5.4 mini" against "judge on the generator", the generator *was* GPT-5.4 mini: both variants used the same model, and both scored the same (88% answered, 100% of out-of-domain refused, 84% citing the expected article). That is a sanity check, not the comparison. The comparison runs when the account resets, with `make eval-answers --variant baseline --variant grounding-on-generator`.

## The fallback, proven by accident

That outage is the best test the fallback of [ADR 0005](0005-provider-fallback-cost-and-observability.md) has had. With the primary provider refusing every call, the service kept answering, the agent kept reviewing, and the only visible change was `usage.model` saying `gpt-5.4-mini` instead of `claude-haiku-4-5`. No code changed and no request failed.

It also left a data point worth following up. With GPT-5.4 mini generating, an answer cost **$0.0076** against **$0.0164** with Haiku the same morning, with 88% answered against 92% (one question). Whether the cheaper model is as correct needs the judged run; if it is, the generator should switch.

## Consequences

- The grounding check and the critic read with a different model from the one that wrote. Until 2026-10-01 they cannot, and nothing says so except the logs: a known gap of running on one provider.
- Changing any role's model is configuration (`LLM_MODEL`, `LLM_JUDGE_MODEL`, `LLM_RERANK_MODEL` and their fallbacks).
- A provider's monthly limit is now a documented failure mode: the spend cap of [ADR 0020](0020-access-spend-and-probes.md) stops the service at its own limit, and the provider's limit moves the service to the other provider.
