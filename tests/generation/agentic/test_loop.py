"""The hand-written loop over a scripted model: when it acts, when it stops, what it records."""

from decimal import Decimal
from typing import Any

import pytest

from app.domain.errors import ReviewGenerationError
from app.domain.schemas.listing_agent_review import StopReason
from app.domain.schemas.listing_review import Listing
from app.foundation.llm.tools import RequestedToolCall, ToolCompletion, ToolSpec
from app.foundation.llm.usage import LLMUsage
from app.generation.agentic.loop import SUBMIT, AgentLoop
from app.generation.agentic.policy import TOOL_PERMISSIONS, AgentRole
from app.generation.agentic.tools import SearchRegulations, ToolResult
from tests.generation.agentic.test_tools import FakeSearch, a_fragment

A_LISTING = Listing(
    text="Piso de dos habitaciones en Chamberí. Fianza de dos meses y honorarios a cargo del inquilino."
)

A_REVIEW: dict[str, Any] = {
    "is_rental_listing": True,
    "findings": [
        {
            "category": "deposit_and_guarantees",
            "severity": "high",
            "message": "La fianza supera una mensualidad",
            "suggestion": "Pide una mensualidad de fianza",
            "legal_basis": "LAU art. 36.1",
            "sources": [36],
        }
    ],
    "verdict": "request_changes",
    "summary": "Hay que corregir la fianza",
}


def usage(cost: str = "0.002") -> LLMUsage:
    return LLMUsage(
        provider="anthropic",
        model="claude-haiku-4-5",
        input_tokens=1_000,
        output_tokens=100,
        latency_ms=500,
        estimated_cost_usd=Decimal(cost),
    )


def calls(*requested: RequestedToolCall, content: str | None = None) -> ToolCompletion:
    return ToolCompletion(
        content=content,
        tool_calls=list(requested),
        usage=usage(),
        message={"role": "assistant", "content": content, "tool_calls": [c.id for c in requested]},
    )


def call(
    name: str, arguments: dict[str, Any] | None = None, *, id: str = "call", malformed: str | None = None
) -> RequestedToolCall:
    return RequestedToolCall(id=id, name=name, arguments=arguments or {}, malformed=malformed)


class ScriptedModel:
    """Answers with the next completion of its script, and records what it was sent."""

    def __init__(self, *script: ToolCompletion, forced: ToolCompletion | None = None) -> None:
        self.script = list(script)
        self.forced = forced
        self.requests: list[dict[str, Any]] = []

    async def complete_with_tools(
        self, *, messages: list[dict[str, Any]], tools: list[ToolSpec], force_tool: str | None = None
    ) -> ToolCompletion:
        self.requests.append({"messages": list(messages), "tools": [t.name for t in tools], "force_tool": force_tool})
        if force_tool is not None:
            assert self.forced is not None, "the loop forced a submission the test did not expect"
            return self.forced
        return self.script.pop(0)


@pytest.fixture(autouse=True)
def grant_the_test_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failing test tool is granted to the reviewer, so these tests exercise failures, not denials."""
    granted = TOOL_PERMISSIONS[AgentRole.REVIEWER] | {"flaky"}
    monkeypatch.setitem(TOOL_PERMISSIONS, AgentRole.REVIEWER, granted)


class FailingTool:
    spec = ToolSpec(name="flaky", description="always fails", parameters={"type": "object", "properties": {}})

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(ok=False, content="Ha fallado")


def a_loop(model: ScriptedModel, **options: Any) -> AgentLoop:
    return AgentLoop(model, [SearchRegulations(FakeSearch()), FailingTool()], **options)


async def test_calls_a_tool_feeds_the_observation_back_and_finishes_on_submit() -> None:
    model = ScriptedModel(
        calls(call("search_regulations", {"query": "fianza"}, id="s1"), content="Voy a buscar la fianza"),
        calls(call(SUBMIT, A_REVIEW, id="done")),
    )

    run = await a_loop(model).run(A_LISTING)

    assert run.stop_reason == StopReason.COMPLETED
    assert run.output.findings[0].sources == [36]
    tool_message = model.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "s1"
    assert tool_message["content"].startswith("[36]")


async def test_collects_every_fragment_the_searches_returned() -> None:
    model = ScriptedModel(calls(call("search_regulations", {"query": "fianza"})), calls(call(SUBMIT, A_REVIEW)))

    run = await a_loop(model).run(A_LISTING)

    assert run.fragments == {36: a_fragment()}


async def test_every_step_lands_in_the_trace_with_the_thought_that_led_to_it() -> None:
    model = ScriptedModel(
        calls(call("search_regulations", {"query": "fianza"}), content="Busco la fianza"),
        calls(call(SUBMIT, A_REVIEW)),
    )

    trace = (await a_loop(model).run(A_LISTING)).trace

    assert [step.tool for step in trace] == ["search_regulations", SUBMIT]
    assert trace[0].thought == "Busco la fianza"
    assert trace[0].arguments == {"query": "fianza"}


async def test_the_usage_of_every_model_call_is_summed() -> None:
    model = ScriptedModel(calls(call("search_regulations", {"query": "fianza"})), calls(call(SUBMIT, A_REVIEW)))

    run = await a_loop(model).run(A_LISTING)

    assert run.usage.estimated_cost_usd == Decimal("0.004")
    assert run.usage.input_tokens == 2_000


async def test_an_invalid_review_goes_back_to_the_model_to_fix() -> None:
    invalid = {**A_REVIEW, "verdict": "maybe"}
    model = ScriptedModel(calls(call(SUBMIT, invalid, id="bad")), calls(call(SUBMIT, A_REVIEW, id="good")))

    run = await a_loop(model).run(A_LISTING)

    assert run.stop_reason == StopReason.COMPLETED
    error = model.requests[1]["messages"][-1]
    assert error["tool_call_id"] == "bad" and "verdict" in error["content"]


async def test_a_failing_tool_is_an_observation_and_the_loop_goes_on() -> None:
    model = ScriptedModel(calls(call("flaky", {"n": 1})), calls(call(SUBMIT, A_REVIEW)))

    run = await a_loop(model).run(A_LISTING)

    assert run.stop_reason == StopReason.COMPLETED
    assert not run.trace[0].ok


async def test_an_unknown_tool_and_malformed_arguments_come_back_as_errors() -> None:
    model = ScriptedModel(
        calls(call("delete_everything", id="a"), call("search_regulations", id="b", malformed="{not json")),
        calls(call(SUBMIT, A_REVIEW)),
    )

    run = await a_loop(model).run(A_LISTING)

    assert [step.ok for step in run.trace[:2]] == [False, False]
    # Deny by default: a tool no role was granted is refused before anything looks it up.
    assert "Llamada denegada" in run.trace[0].result


async def test_the_same_call_failing_twice_stops_the_loop_and_forces_a_submission() -> None:
    model = ScriptedModel(
        calls(call("flaky", {"n": 1})),
        calls(call("flaky", {"n": 1})),
        forced=calls(call(SUBMIT, A_REVIEW)),
    )

    run = await a_loop(model).run(A_LISTING)

    assert run.stop_reason == StopReason.TOOL_ERROR
    assert model.requests[-1]["force_tool"] == SUBMIT


async def test_stops_at_the_iteration_limit_with_what_the_model_has() -> None:
    model = ScriptedModel(
        *[calls(call("search_regulations", {"query": f"tema {i}"})) for i in range(3)],
        forced=calls(call(SUBMIT, A_REVIEW)),
    )

    run = await a_loop(model, max_iterations=3).run(A_LISTING)

    assert run.stop_reason == StopReason.MAX_ITERATIONS
    assert len(model.requests) == 4
    assert model.requests[-1]["tools"] == [SUBMIT]


async def test_stops_when_the_time_is_up() -> None:
    model = ScriptedModel(forced=calls(call(SUBMIT, A_REVIEW)))

    run = await a_loop(model, timeout_seconds=-1).run(A_LISTING)

    assert run.stop_reason == StopReason.TIMEOUT


async def test_an_answer_without_tools_is_nudged_back_to_the_tools() -> None:
    model = ScriptedModel(calls(content="Creo que está bien"), calls(call(SUBMIT, A_REVIEW)))

    run = await a_loop(model).run(A_LISTING)

    assert run.stop_reason == StopReason.COMPLETED
    assert model.requests[1]["messages"][-1]["role"] == "user"


async def test_a_forced_submission_that_is_still_invalid_is_a_generation_error() -> None:
    model = ScriptedModel(forced=calls(call(SUBMIT, {"summary": "incompleto"})))

    with pytest.raises(ReviewGenerationError):
        await a_loop(model, timeout_seconds=-1).run(A_LISTING)
