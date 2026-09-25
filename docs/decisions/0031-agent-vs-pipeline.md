# 0031. Agent vs pipeline, measured: the pipeline reviews, the agent's actor sees more, and its critic subtracts for now

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #52 (part of #4)

## Context

Every agent phase (#38 to #43) claimed the agent is worth its extra calls. [ADR 0030](0030-listing-review-evaluation.md) measured both paths once on the 18 annotated listings and found the agent worse on every quality metric but the adversarial ones, with a trace that put the blame on the critic. This phase fixes what the trace showed, measures again, breaks the cost down by step, and classifies the failures, so that "is the agent worth it" is answered by listing kind, not by conviction.

**A confound to keep in mind throughout:** Anthropic is at its monthly limit until 2026-10-01, so the actor falls back to GPT-5.4 mini, the critic's model. [ADR 0023](0023-a-model-per-role.md) put the critic on the other provider so it would not share the actor's blind spots; everything below measures the critic **on the same model as the actor**, which is the configuration that decision was meant to avoid.

## Decision

### What changed before measuring

| Change | Why (the trace of ADR 0030) |
|---|---|
| Critic prompt v3: a paragraph is not an article; the checklist does not limit findings that cite fragments | The critic rejected the four omissions of Catalan article 61 as "art. 61.2, not the article of 61.2.c, and not in the checklist" |
| Code check: a `wrong_article` rejection does not stand when every fragment the finding cites is the article it names | The same error, made impossible rather than discouraged, as the quote check of [ADR 0025](0025-actor-critic-boss.md) does for `contradicts_listing` |
| Agent prompt v4: the pipeline's checklist v3 and its rule on notes claiming a prior review | Three of four clean listings got a legal finding from the checklist v2 |
| `CostBreakdown` per step (actor turns, tools, critic, rewrite), returned by the API and shown in the UI | #52's contract, so the next optimisation is read, not argued |
| The runner classifies each failure by the step that lost it, from the trace | An article never read (search), read and not reported (actor), reported and rejected (critic), or reported without being expected (invented) |

### Results

The same 18 listings (GPT-5.4 mini as actor and critic, one run each unless stated):

| Path | Precision | Recall | F1 | Clean false positives | Verdict | Adversarial | Cost / review | p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Pipeline, prompt v3** | **100%** | 81% | **0.90** | **0%** | **87%** | 100% | **$0.0017** | **2.7 s** |
| Agent before #52 (ADR 0030) | 67% | 75% | 0.71 | 75% | 67% | 100% | $0.0297 | 12.8 s |
| Agent, critic v3 and prompt v4 | 55% | 75% | 0.63 | 25% | 67% | 100% | $0.0228 | 10.1 s |
| Agent without its critic | 58% | **94%** | 0.71 | 50% | 80% | 100% | $0.0132 | 8.9 s |

The two Catalan listings, three more runs of the agent with its critic: Barcelona's article 61 published in **0 of 3** (twice never reported, once reported and rejected by the critic); Girona's in 2 of 3, and its fee finding lost to the critic in 2 of 3.

**Failures, by the step that lost them:**

| Failure | Pipeline v3 | Agent | Agent without critic |
|---|---:|---:|---:|
| Expected article never read | | 0 | 0 |
| Read, not reported (actor) | | 1 | 1 |
| Reported, rejected by the critic | | 3 | |
| Missed (the pipeline has no trace) | 3 | | |
| Invented: an article the listing does not break | 0 | 10 | 11 |
| Wrong verdict | 2 | 5 | 3 |

**Cost per completed agent review, by step** ($0.0274; the table above divides by every listing, refusals included): the actor's turns are **86%** ($0.0237: each turn re-reads the whole conversation, fragments included), the critic 14%, the tools nothing (the embedding of a query is below the rounding).

### What the numbers say

1. **The search is not the problem.** No expected article was ever missed because the agent did not read it; retrieval, measured since [ADR 0012](0012-retrieval-baseline-and-tuning.md), does its part.
2. **The actor is the agent's asset.** Without the critic it finds 94% of the expected articles, the highest of any path, and it is the only path that finds the Catalan law (all three omissions of article 61 in Barcelona, which the pipeline cannot see by construction).
3. **The actor's problem is what it adds.** Half of its extra findings are confirmations with a legal basis ("La fianza indicada es correcta para una vivienda habitual"; one clean listing got five of them), the other half advice ("conviene concretar...") dressed as law. It also marks the Catalan omissions below `high`, so Barcelona is approved with its three findings listed.
4. **The critic, on the same model, subtracts.** It lowers recall from 94% to 75% and the verdict from 80% to 67%, for 70% more cost, and it does not buy precision either (58% without it, 55% with it); its one gain is on clean listings (50% → 25% with a legal finding). It rejected correct findings as contradicting the listing (a four-month guarantee, a price with no concepts, an energy rating "en trámite"), each time quoting a sentence that is in the listing, so the quote check let the rejection stand: that check stops a critic that invents a contradiction, not one that misreads a real sentence. It rejected Girona's fee finding (LAU art. 20.1, the right article) as the wrong article in two of three repeats, outside the code check because the finding did not cite only that article. And it rejected the omissions of article 61 in three of the six Catalan repeats, while letting the actor's confirmations through.

### When each path is worth it

- **The pipeline reviews listings**: it is the best on F1, precision, verdict, cost (8 times cheaper than the agent without its critic, 13 times with it) and latency. It is what the main review page and `POST /listings/review` serve.
- **The agent is worth it where the checklist is blind**: a regional law the pipeline does not carry. Today that is Catalonia, and today it finds it only without its critic, and sometimes with its critic. Routing Catalan listings to the agent is the design this points to; it is not built until the agent's precision holds on those listings.
- **The critic stays in the design and on by default**, because it is the gate of the human pause ([ADR 0027](0027-human-in-the-loop.md)), and because what was measured is not the design: an actor and a critic sharing a model. It is measured again when the actor is Claude Haiku 4.5 (from 2026-10-01, with the cross-provider judge of #47). If a critic on the other provider still subtracts, it becomes a flag for a person instead of a filter that removes findings.

## Consequences

- **What to optimise next, by the breakdown:** the actor's context (86% of the cost), not the critic or the tools. Trimming fragments already read from later turns, or one search per theme instead of re-searching on a retry, is where the money is.
- **What to fix next, by the failure table:** the actor's confirmations (the largest single failure) and the severity of regional omissions. Both are prompt rules measurable on this dataset in one run (~$0.25 without the critic).
- The issue asked for five repeats of every listing. The budget of the account ($4 left, $1.5 of it reserved for the public demo) paid for one run of each configuration and three repeats of the listings the decision depends on (Catalonia). The runner does any number (`--repeat`).
- All the measurements of this phase cost **$0.82**.
- [ADR 0024](0024-agent-loop-and-tools.md) predicted that the agent's extra calls buy regional law; measured, they do, and they also buy invented findings the pipeline does not make.
