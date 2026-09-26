# 0035. The critic flags, it does not filter

- **Status**: Accepted
- **Date**: 2026-09-26
- **Issue**: follow-up of #52 ([ADR 0031](0031-agent-vs-pipeline.md))

## Context

[ADR 0031](0031-agent-vs-pipeline.md) measured the agent's critic on the same model as its actor (GPT-5.4 mini for both, because the Anthropic account was at its monthly limit) and found that it subtracts: recall 94% → 75% and verdict 80% → 67%, rejecting correct findings. It wrote the next step in advance: measure again with the actor on Claude Haiku 4.5, so the critic reads another provider's work as [ADR 0023](0023-a-model-per-role.md) designed, and **if a critic on the other provider still subtracts, it becomes a flag for a person instead of a filter that removes findings.**

The Anthropic account came back on 2026-09-26, and this is that measurement.

## What was measured

The 18 annotated listings, Claude Haiku 4.5 as the actor and GPT-5.4 mini as the critic, one run each:

| Agent | Precision | Recall | F1 | Clean false positives | Verdict | Escalated | Findings removed | Cost / review | p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Critic filters (agent v4, checklist v3) | 100% | 75% | 0.86 | 0% | 80% | 20% | 7 | $0.0275 | 14.9 s |
| No critic (agent v4, checklist v3) | 100% | **94%** | **0.97** | 0% | **93%** | 0% | 0 | $0.0239 | 13.2 s |
| **Critic flags (agent v5, checklist v4)** | **100%** | **94%** | **0.97** | **0%** | **93%** | 20% | **0** | $0.0251 | 15.1 s |
| _For reference: the pipeline v4 with Haiku ([ADR 0030](0030-listing-review-evaluation.md))_ | _100%_ | _75%_ | _0.86_ | _0%_ | _87%_ | | | _$0.0035_ | _3.7 s_ |

1. **On the other provider, the critic still subtracts.** As a filter it removed 7 findings and lowered recall from 94% to 75%: both Catalan omissions of Ley 18/2007 art. 61, which the pipeline cannot see by construction, and the excessive guarantee of LAU art. 36.5.
2. **Its doubts were wrong every time.** In the flag run it disputed 5 findings in 3 listings, and all 5 were expected findings of the annotation: LAU art. 20 in `madrid-three-violations`, RD 390/2021 art. 15 and Ley 12/2023 art. 31 in `no-surface-no-rating-deposit`, and Ley 18/2007 art. 61 twice in `girona-fees-and-offer`.
3. **The actor was the problem ADR 0031 blamed, and it was the model.** With GPT-5.4 mini acting, the agent invented 10-11 findings (confirmations such as "la fianza indicada es correcta" with a legal basis). With Claude Haiku 4.5 acting it invented none, with or without the critic. Precision went from 55-58% to 100%.

## Decision

**`AGENT_CRITIC_MODE=flag` is the default.** The critic still reads every finding against the listing and the fragments, but what it does not back is **kept**, with its problem and reason, and the review goes to a person through the human pause of [ADR 0027](0027-human-in-the-loop.md):

- The boss escalates when the critic doubts anything and accepts when it doubts nothing. It never sends the actor back: the retry is where correct findings were lost (ADR 0030, ADR 0031).
- The API returns the doubts in `disputed_findings`, and a paused review lists them among the proposed findings, each with the critic's reason, so the person decides on each one.
- A doubted `high` finding still counts for the verdict: the review does not approve a listing because the critic hesitated.
- `filter` stays available (`AGENT_CRITIC_MODE=filter`, `make eval-listings --critic-mode filter`) as the comparison, and it is still the class default so ADR 0025's tests keep describing it.

## Consequences

- **The agent now reviews better than the pipeline on every quality metric**: F1 0.97 against 0.86, verdict 93% against 87%, and it finds the Catalan law. It costs about 7 times more ($0.025 against $0.0035) and takes about 4 times longer (15 s against 3.7 s), and one review in five waits for a person. Routing Catalan listings, or all listings, to the agent is now a product decision on cost and latency, no longer a question of quality.
- **A person's time is the critic's new cost**, and on this run it bought nothing: 0 of its 5 doubts were right. If that holds over more runs, the next step is to change what the critic checks or to drop it, and to keep the human pause for the cases a code check can recognise (a regional law, an irreversible action), as the course suggests.
- One run of each configuration. Every difference that decides something here is several listings wide, far above the one-listing noise measured in ADR 0030. The three agent runs cost **$1.38**.
