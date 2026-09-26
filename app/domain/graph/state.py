"""The state of a review run, as the graph keeps it between nodes and the checkpointer keeps it on disk.

**Plain JSON only.** The checkpoint is written to Postgres and read back, possibly by another process
after a restart. LangGraph can serialise our dataclasses and Pydantic models, but reading them back
means importing classes named in a database row, which its next versions block by default and which
is a risk anyway. So the state holds dicts, lists, strings and numbers, and every node converts at
its edges: typed objects in the code, JSON in the checkpoint.

**Reducers for what accumulates.** A node returns only what it added: the messages, the trace, the
usage and the fragments are appended or merged, never replaced. Two nodes writing a plain list would
race, and the last write would win (the "state clobbering" of the multi-agent session).
"""

import operator
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from app.domain.schemas.listing_agent_review import TraceStep
from app.foundation.llm.usage import LLMUsage
from app.generation.agentic.ports import RegulationFragment


def merge(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    return {**existing, **new}


class ReviewState(TypedDict, total=False):
    listing: dict[str, Any]
    messages: Annotated[list[dict[str, Any]], operator.add]
    # The tool calls the last model turn asked for, replaced every turn.
    pending: list[dict[str, Any]]
    # What the model wrote next to its last tool calls: its reasoning, for the trace.
    thought: str | None
    # chunk id (as a string: JSON keys are strings) → fragment. The only fragments a finding may cite.
    fragments: Annotated[dict[str, dict[str, Any]], merge]
    trace: Annotated[list[dict[str, Any]], operator.add]
    usage: Annotated[list[dict[str, Any]], operator.add]
    iterations: int
    failures: dict[str, int]
    deadline: float
    candidate: dict[str, Any] | None
    stop_reason: str | None
    attempt: int
    critic: dict[str, Any] | None
    # accept, escalate, or not_a_listing: where the run ended.
    outcome: str | None
    # What a person decided on a paused run (#42), as the resume command carried it.
    human_decision: dict[str, Any] | None


# ── Conversions at the edges ────────────────────────────────────────────────────────────────


def usage_to_json(usage: LLMUsage) -> dict[str, Any]:
    data = asdict(usage)
    data["estimated_cost_usd"] = str(usage.estimated_cost_usd) if usage.estimated_cost_usd is not None else None
    return data


def usage_from_json(data: dict[str, Any]) -> LLMUsage:
    cost = data.get("estimated_cost_usd")
    return LLMUsage(**{**data, "estimated_cost_usd": Decimal(cost) if cost is not None else None})


def fragment_to_json(fragment: RegulationFragment) -> dict[str, Any]:
    return asdict(fragment)


def fragments_from_json(data: dict[str, dict[str, Any]]) -> dict[int, RegulationFragment]:
    return {int(chunk_id): RegulationFragment(**fragment) for chunk_id, fragment in data.items()}


def step_to_json(step: TraceStep) -> dict[str, Any]:
    return step.model_dump(mode="json")
