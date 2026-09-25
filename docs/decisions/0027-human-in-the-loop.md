# 0027. A review the agent cannot stand behind waits for a person

- **Status**: Accepted
- **Date**: 2026-09-25
- **Issue**: #42 (part of #3)

## Context

The boss of [ADR 0025](0025-actor-critic-boss.md) escalates a review when the critic cannot back enough of its findings, even after a retry. Until now an escalation was a flag in the response and a banner in the UI: the review was published anyway, with a warning. The session on orchestration asks for the opposite at the critical point: the graph pauses with `interrupt`, its state checkpointed, and resumes with a person's decision, minutes or days later, on any process. The session on multi-agent systems adds that a person should be woken only when needed: high-confidence runs flow straight through.

## Decision

**An escalated review stops before it is published.** A `human_gate` node after the boss calls `interrupt()` when the boss escalated, and nothing else reaches it. The API answers `202` with the run id, the review the agent proposes, and the findings the critic rejected with its reasons, so the person sees both sides.

A person then decides, through `POST /api/v1/listings/agent-review/{run_id}/resume`:

| Action | What is published |
|---|---|
| `approve` | The proposed review, as it is |
| `adjust` | Only the proposed findings the person keeps (`keep`, their positions) |
| `reject` | Nothing: the review is discarded |

`GET /api/v1/listings/agent-review/{run_id}` returns a paused review again, so the page can be reloaded without losing the decision to make. The UI keeps the run id in the session and renders the proposed findings as checkboxes, the rejected ones with the critic's reason, and the three actions.

- **The pause is read from the checkpoint, never stored as a status.** Whether a run is waiting is whether its graph has a next node. A `status = 'paused'` column would be a second record of the same fact, and a crash between the interrupt and that write would leave it lying.
- **The decision is logged before the graph resumes** (`agent_review.human_decision`, with the action and the findings kept, never the note's text), so a crash in between leaves the decision on record rather than losing it silently.
- **Retention.** A paused run is the only state the service keeps, because it has to: its checkpoint holds the listing. It is deleted as soon as it is resumed.
- **Only when needed.** Accepted reviews never reach the gate. `AGENT_HUMAN_REVIEW_ENABLED=false` turns the gate into the old flag. The hand-written loop cannot pause (it has no checkpoint), which is one of the reasons the graph is the default ([ADR 0026](0026-langgraph-orchestration.md)).

### Why the decision is about the findings, not the listing

The plan tied "adjust" to the rewritten listing of #39, which does not exist yet. A person choosing which conclusions stand is the decision the escalation is about: the critic doubted some findings, and a person settles which. When the rewrite lands, `adjust` grows a corrected text; the pause does not change.

## Checked across two processes, on Postgres

The claim that matters is that a pause survives the process that made it. Checked with the Madrid listing, the acceptance threshold set above 100% to force an escalation:

1. **Process A** reviewed the listing: five proposed findings, paused, **one thread left** in `checkpoints`, $0.0185. The process ended.
2. **Process B**, a new Python process as after a restart, read the pending review from the checkpoint, applied `adjust` keeping the energy label and the deposit findings, and the graph ran to its end: two findings published, **no thread left**.

## Consequences

- A review can take as long as the person does. The API answers at once with `202` and the person resumes whenever they come back.
- Paused runs accumulate if nobody decides. There is no expiry yet: a paused review older than N days should be discarded by a scheduled job (`adelete_thread`), and that is listed in the limitations.
- The notification channel is the UI: a person sees a paused review when they open it. An email or Slack message when a review pauses is the next step the session mentions, and a hook on the `agent_review.paused` event is where it would go.
