"""The agent review as a LangGraph graph: the same flow as the hand-written loop, declared instead of nested.

```
START → plan ─┬─(tool calls)──→ act ─┬─(review submitted)→ critic ─┬─→ boss ─┬─(retry)──→ plan
              │                      ├─(same call failed twice)─┐   └─(not a listing)→ END
              ├─(no tool call)→ plan └─(otherwise)→ plan        │             ├─(accept)→ END
              └─(out of steps or time)→ force_submit ←──────────┘             └─(escalate)→ human_gate → END
                                         └──→ critic                                  (paused until a person decides)
```

What the graph adds over the loop of `app/generation/agentic/loop.py` (ADR 0026):

- **The state is persisted after every node** by the checkpointer, keyed by the run id. A run is a
  row that can be inspected, and the human pause of #42 is a node that stops the graph and resumes
  it, on this process or another one, later.
- **Routing is data.** Every edge is declared here and every exit is a condition on the state,
  instead of a `break` inside a `for` inside a `while`.
- **The retry continues the conversation.** When the boss sends the actor back, it gets the critic's
  rejections as the next message and keeps the fragments it already read, where the loop starts over.

The hard exits are the loop's, as conditions in `plan`: the graph's own recursion limit is a
backstop that should never be the thing that stops a run.
"""

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.domain.errors import ReviewGenerationError
from app.domain.graph.state import (
    ReviewState,
    fragment_to_json,
    fragments_from_json,
    step_to_json,
    usage_to_json,
)
from app.domain.schemas.listing_agent_review import AgentFinding, AgentReviewCandidate, Step, StopReason, TraceStep
from app.domain.schemas.listing_review import Listing
from app.foundation.llm.tools import RequestedToolCall, ToolCallingLLM
from app.foundation.llm.wrapper import StructuredLLM
from app.generation.agentic.boss import BossDecision, decide
from app.generation.agentic.critic import (
    CriticResult,
    Problem,
    Rejection,
    boss_step,
    critic_step,
    criticise,
    feedback_for,
)
from app.generation.agentic.loop import (
    FINAL_CALL,
    NUDGE_TO_SUBMIT,
    RESULT_PREVIEW_CHARS,
    SUBMIT,
    SUBMIT_SPEC,
    ToolBox,
    parse_submission,
    tool_message,
)
from app.generation.agentic.ports import RegulationSearch
from app.generation.agentic.tools import CheckListingFields, SearchRegulations

NOT_A_LISTING = "not_a_listing"


@dataclass(frozen=True)
class GraphConfig:
    max_iterations: int = 6
    timeout_seconds: float = 90.0
    max_attempts: int = 2
    min_confidence: float = 0.7
    escalate_below: float = 0.4
    max_fragments: int = 5
    # An escalated review pauses for a person before it is published (#42). Off, it only carries the flag.
    human_review: bool = True

    @property
    def recursion_limit(self) -> int:
        """A backstop above what the run's own exits allow: plan and act per step, plus the tail."""
        return (2 * self.max_iterations + 4) * self.max_attempts + 10


def build_review_graph(
    *,
    llm: ToolCallingLLM,
    search: RegulationSearch,
    critic: StructuredLLM | None,
    config: GraphConfig,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    def toolbox_for(state: ReviewState) -> ToolBox:
        listing = Listing.model_validate(state["listing"])
        return ToolBox([CheckListingFields(listing), SearchRegulations(search, max_fragments=config.max_fragments)])

    specs = ToolBox([CheckListingFields(Listing(text="")), SearchRegulations(search)]).specs

    async def plan(state: ReviewState) -> dict[str, Any]:
        iterations = state.get("iterations", 0)
        if iterations >= config.max_iterations:
            return {"stop_reason": StopReason.MAX_ITERATIONS.value, "pending": []}
        if time.time() > state["deadline"]:
            return {"stop_reason": StopReason.TIMEOUT.value, "pending": []}

        completion = await llm.complete_with_tools(messages=state["messages"], tools=specs)
        update: dict[str, Any] = {
            "messages": [completion.message],
            "usage": [usage_to_json(completion.usage)],
            "iterations": iterations + 1,
            "pending": [asdict(call) for call in completion.tool_calls],
            "thought": completion.content,
        }
        if not completion.tool_calls:
            update["messages"] = [completion.message, {"role": "user", "content": NUDGE_TO_SUBMIT}]
            step = TraceStep(
                step=len(state.get("trace", [])) + 1, tool="(sin herramienta)", thought=completion.content, ok=False
            )
            update["trace"] = [step_to_json(step)]
        return update

    async def act(state: ReviewState) -> dict[str, Any]:
        toolbox = toolbox_for(state)
        base = len(state.get("trace", []))
        messages: list[dict[str, Any]] = []
        trace: list[TraceStep] = []
        fragments: dict[str, dict[str, Any]] = {}
        failures = dict(state.get("failures", {}))
        thought = state.get("thought")
        candidate: AgentReviewCandidate | None = None
        stop: str | None = None

        for raw in state.get("pending", []):
            call = RequestedToolCall(**raw)
            if candidate is not None:
                # Every call needs its answer in the conversation, or a retry could not continue it.
                messages.append(tool_message(call, "Ignorada: la revisión ya se ha entregado."))
                continue
            if call.name == SUBMIT:
                candidate, error = parse_submission(call)
                trace.append(
                    TraceStep(
                        step=base + len(trace) + 1,
                        tool=SUBMIT,
                        ok=candidate is not None,
                        result="Revisión entregada" if candidate else error,
                        thought=thought,
                    )
                )
                thought = None
                messages.append(tool_message(call, "Revisión entregada" if candidate else error))
                continue

            result, latency_ms = await toolbox.execute(call)
            for fragment in result.data.get("fragments") or []:
                fragments[str(fragment.chunk_id)] = fragment_to_json(fragment)
            trace.append(
                TraceStep(
                    step=base + len(trace) + 1,
                    tool=call.name,
                    arguments=call.arguments,
                    result=result.content[:RESULT_PREVIEW_CHARS],
                    ok=result.ok,
                    latency_ms=latency_ms,
                    thought=thought,
                )
            )
            thought = None
            messages.append(tool_message(call, result.content))
            if not result.ok:
                key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
                failures[key] = failures.get(key, 0) + 1
                if failures[key] >= 2:
                    stop = StopReason.TOOL_ERROR.value

        update: dict[str, Any] = {
            "messages": messages,
            "trace": [step_to_json(step) for step in trace],
            "fragments": fragments,
            "failures": failures,
            "pending": [],
        }
        if candidate is not None:
            update["candidate"] = candidate.model_dump(mode="json")
        elif stop is not None:
            update["stop_reason"] = stop
        return update

    async def force_submit(state: ReviewState) -> dict[str, Any]:
        """Out of steps, time or luck: one forced call to hand in what the actor has."""
        ask = {"role": "user", "content": FINAL_CALL}
        completion = await llm.complete_with_tools(
            messages=[*state["messages"], ask], tools=[SUBMIT_SPEC], force_tool=SUBMIT
        )
        base = len(state.get("trace", []))
        for call in completion.tool_calls:
            if call.name != SUBMIT:
                continue
            candidate, error = parse_submission(call)
            step = TraceStep(step=base + 1, tool=SUBMIT, ok=candidate is not None, result=error or "Revisión entregada")
            if candidate is not None:
                return {
                    "messages": [ask, completion.message, tool_message(call, "Revisión entregada")],
                    "usage": [usage_to_json(completion.usage)],
                    "trace": [step_to_json(step)],
                    "candidate": candidate.model_dump(mode="json"),
                }
        raise ReviewGenerationError(f"the agent stopped ({state.get('stop_reason')}) without a valid review")

    async def critic_node(state: ReviewState) -> dict[str, Any]:
        candidate = AgentReviewCandidate.model_validate(state["candidate"])
        if not candidate.is_rental_listing:
            return {"outcome": NOT_A_LISTING}
        if critic is None:
            return {"critic": critic_to_json(CriticResult(supported=list(candidate.findings)))}

        result = await criticise(
            candidate.findings,
            Listing.model_validate(state["listing"]),
            fragments_from_json(state.get("fragments", {})),
            critic,
        )
        update: dict[str, Any] = {
            "critic": critic_to_json(result),
            "trace": [step_to_json(critic_step(len(state.get("trace", [])) + 1, result))],
        }
        if result.usage is not None:
            update["usage"] = [usage_to_json(result.usage, Step.CRITIC)]
        return update

    async def boss_node(state: ReviewState) -> dict[str, Any]:
        result = critic_from_json(state["critic"] or {})
        attempt = state.get("attempt", 1)
        decision = decide(
            result,
            attempt=attempt,
            max_attempts=config.max_attempts,
            min_confidence=config.min_confidence,
            escalate_below=config.escalate_below,
        )
        update: dict[str, Any] = {"trace": [step_to_json(boss_step(len(state.get("trace", [])) + 1, decision))]}
        if decision == BossDecision.RETRY:
            # The actor keeps the conversation and the fragments it read, and hears why.
            update |= {
                "messages": [{"role": "user", "content": feedback_for(result.rejected)}],
                "attempt": attempt + 1,
                "candidate": None,
                "critic": None,
                "stop_reason": None,
                "iterations": 0,
                "deadline": time.time() + config.timeout_seconds,
            }
        else:
            update["outcome"] = decision.value
        return update

    def after_plan(state: ReviewState) -> str:
        if state.get("stop_reason"):
            return "force_submit"
        return "act" if state.get("pending") else "plan"

    def after_act(state: ReviewState) -> str:
        if state.get("candidate") is not None:
            return "critic"
        return "force_submit" if state.get("stop_reason") else "plan"

    def after_critic(state: ReviewState) -> str:
        return END if state.get("outcome") == NOT_A_LISTING else "boss"

    async def human_gate(state: ReviewState) -> dict[str, Any]:
        """The run stops here and the checkpoint keeps it, for minutes or days, until a person decides.

        Whether a run is waiting is read from the checkpoint, never stored as a status of its own:
        a second record of the same fact is one a crash between two writes would leave lying.
        """
        decision = interrupt({"reason": "escalated", "attempt": state.get("attempt", 1)})
        return {"human_decision": decision}

    def after_boss(state: ReviewState) -> str:
        outcome = state.get("outcome")
        if not outcome:
            return "plan"
        if outcome == BossDecision.ESCALATE.value and config.human_review:
            return "human_gate"
        return END

    graph = StateGraph(ReviewState)
    graph.add_node("plan", plan)
    graph.add_node("act", act)
    graph.add_node("force_submit", force_submit)
    graph.add_node("critic", critic_node)
    graph.add_node("boss", boss_node)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", after_plan, ["plan", "act", "force_submit"])
    graph.add_conditional_edges("act", after_act, ["plan", "critic", "force_submit"])
    graph.add_edge("force_submit", "critic")
    graph.add_conditional_edges("critic", after_critic, ["boss", END])
    graph.add_node("human_gate", human_gate)
    graph.add_conditional_edges("boss", after_boss, ["plan", "human_gate", END])
    graph.add_edge("human_gate", END)
    return graph.compile(checkpointer=checkpointer)


# ── The critic's verdict, as the checkpoint keeps it ────────────────────────────────────────


def critic_to_json(result: CriticResult) -> dict[str, Any]:
    return {
        "supported": [finding.model_dump(mode="json") for finding in result.supported],
        "rejected": [
            {"finding": r.finding.model_dump(mode="json"), "problem": r.problem.value, "reason": r.reason}
            for r in result.rejected
        ],
        "confidence": result.confidence,
        "unavailable": result.unavailable,
    }


def critic_from_json(data: dict[str, Any]) -> CriticResult:
    return CriticResult(
        supported=[AgentFinding.model_validate(finding) for finding in data.get("supported", [])],
        rejected=[
            Rejection(
                finding=AgentFinding.model_validate(r["finding"]), problem=Problem(r["problem"]), reason=r["reason"]
            )
            for r in data.get("rejected", [])
        ],
        confidence=float(data.get("confidence", 1.0)),
        unavailable=bool(data.get("unavailable", False)),
    )
