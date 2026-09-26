# 0025. Actor, critic, boss: no finding the listing or the law does not hold

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #40 (part of #3)

## Context

The agent of [ADR 0024](0024-agent-loop-and-tools.md) proves structure: a legal finding cites a fragment the agent read. It cannot prove meaning, and the hand checks of #38 showed both ways it goes wrong: a finding whose cited article does not say what it claims, and a finding about the listing that the listing contradicts (a rating reported missing that the listing stated). The session on actor-critic-boss gives the pattern: an actor that writes, a critic that only judges with typed feedback, and a boss that decides with a hard limit on attempts.

## Decision

- **Actor**: the agent loop of #38.
- **Critic** (`app/generation/agentic/critic.py`): one call per review, on the **judge's model**, the other provider from the actor's ([ADR 0023](0023-a-model-per-role.md)). It reads each finding against the listing and against the **whole** text of the articles it cites, and returns, per finding, `supported` and a typed `problem`: `contradicts_listing`, `rule_not_in_sources`, `wrong_article` or `none`. It never rewrites or adds a finding.
- **Boss** (`app/generation/agentic/boss.py`): a function, not a model. Three outcomes and two thresholds are an `if`: **accept** at 70% of findings supported, **retry** once in between (the actor runs again with the rejected findings and the critic's reasons quoted back), **escalate** below 40% or when the retries are spent. A rejected finding never reaches the user, and an escalated review says a person has to check it.
- **The model quotes, code checks**, on both sides:
  - every finding about what the listing says carries `evidence`, the listing's own sentence, and a finding whose quote is not in the listing is dropped before any model is asked about it;
  - the critic can only claim `contradicts_listing` with a `quote` of the listing that code finds; without it, its word does not remove a finding.

  The check folds case, accents and punctuation and tolerates a copying slip, and it cannot tell a slip from a dropped "no": it stops invented sentences, and whether a real sentence supports a finding stays the critic's job.
- A critic that cannot run keeps every finding and says so in the trace: its absence is not evidence against the findings.

## How it got here: three versions, each found by hand on two real listings

The same two listings as ADR 0024 (Madrid, with three violations; Barcelona, a clean studio), $0.17 in all. With the Anthropic account at its monthly limit (ADR 0023), every run used GPT-5.4 mini for both actor and critic.

| Version | Madrid | Barcelona | What it showed |
|---|---|---|---|
| Critic v1 | ❌ The critic **rejected the correct deposit finding** as contradicting a listing that said "Se piden dos meses de fianza"; on the retry the actor dropped it | ❌ The actor **invented a violation** ("the fees are charged to the tenant" in a listing that puts them on the landlord) and the critic let it through | A critic's word is not enough, and neither is the actor's |
| Quotes checked in code (actor v3, critic v2) | ✅ All three violations kept and cited | Escalated: the critic rejected findings on Catalan article 61 as "not in the sources" | The findings were right and the sources were cut: **articles were truncated at 1,500 characters**, and the tail of article 61 (1,942) was invisible to both |
| Whole articles to the critic, 3,000 characters per search result | ✅ All four findings accepted, nothing escalated | Escalated: the critic rejects the actor's noisy findings on a clean listing ("the municipality is missing from the text, although it is in the fields"), each with a quote code verified | The critic doing its job; the actor on GPT-5.4 mini produces noise on a clean listing, and the boss hands it to a person |

The truncation was a real bug outside the pattern: 10% of the corpus's articles are longer than 3,482 characters, and a rule cut off at the end of an article is a rule nobody can see. The critic now reads the cited articles whole (at most 6,000 characters, the longest a chunk can be).

## Consequences

- A review costs one more model call (~$0.002-0.005), and up to a second actor run on a retry. #52 measures it on the listings dataset.
- **Escalation on clean listings is the open question.** Two listings are an anecdote; #52 measures the escalation rate and the findings each version keeps on 18-20 annotated listings, with the actor back on Claude Haiku 4.5 from 2026-10-01. If clean listings keep being escalated, the lever is the actor's prompt, not the critic's thresholds.
- Escalation is where the human pause of #42 starts: today it is a flag in the response and a banner in the UI; with the graph it becomes a paused run that waits for a decision.
