"""The review as a graph, over scripted models and an in-memory checkpointer."""

import json
from decimal import Decimal
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.domain.agent_review_service import AgentReviewService
from app.domain.errors import LLMUnavailable, NotAListing
from app.domain.graph.state import fragment_to_json, fragments_from_json, usage_from_json, usage_to_json
from app.domain.schemas.listing_agent_review import StopReason
from app.domain.schemas.listing_review import Listing, Verdict
from app.foundation.llm.tools import ToolSpec
from app.foundation.llm.usage import LLMUsage
from app.generation.agentic.loop import SUBMIT
from tests.domain.test_agent_review_service import A_LISTING, TWO_FINDINGS, critic_of, finding, review_with
from tests.generation.agentic.test_loop import A_REVIEW, ScriptedModel, call, calls
from tests.generation.agentic.test_tools import FakeSearch, a_fragment


class Checkpoints:
    """An in-memory saver the test can look into after the run."""

    def __init__(self) -> None:
        self.saver = InMemorySaver()

    async def __call__(self) -> InMemorySaver:
        return self.saver


def graph_service(
    model: Any, *, critic: Any = None, checkpoints: Checkpoints | None = None, **options: Any
) -> AgentReviewService:
    return AgentReviewService(model, FakeSearch(), critic=critic, checkpoints=checkpoints or Checkpoints(), **options)


def searches_then_submits(review: dict[str, Any]) -> list[Any]:
    return [
        calls(call("search_regulations", {"query": "fianza"}), content="Busco la fianza"),
        calls(call(SUBMIT, review)),
    ]


async def test_a_review_runs_as_a_graph_and_ends_with_cited_findings() -> None:
    reviewed = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), critic=critic_of([True])).review(
        A_LISTING
    )

    assert reviewed.run_id is not None
    assert reviewed.stop_reason == StopReason.COMPLETED
    assert reviewed.review.findings[0].citations[0].url.endswith("#a36")
    assert [step.tool for step in reviewed.trace] == ["search_regulations", SUBMIT, "critic", "boss"]
    assert reviewed.trace[0].thought == "Busco la fianza"


async def test_the_trace_and_the_usage_accumulate_across_nodes() -> None:
    reviewed = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), critic=critic_of([True])).review(
        A_LISTING
    )

    # Two actor turns at $0.002 and the critic at $0.0024: appended by the reducers, never replaced.
    assert reviewed.usage.estimated_cost_usd == Decimal("0.0064")
    assert [step.step for step in reviewed.trace] == [1, 2, 3, 4]


async def test_a_retry_continues_the_conversation_with_the_rejections() -> None:
    model = ScriptedModel(
        *searches_then_submits(TWO_FINDINGS),
        calls(call(SUBMIT, review_with(finding(legal_basis="LAU art. 36.1", sources=[36])))),
    )

    reviewed = await graph_service(model, critic=critic_of([True, False], [True])).review(A_LISTING)

    third_turn = model.requests[2]["messages"]
    # Unlike the loop, the actor keeps what it read: its first search is still in the conversation.
    assert any(m.get("role") == "tool" and m["content"].startswith("[36]") for m in third_turn)
    assert "Un revisor ha comprobado tu revisión anterior" in third_turn[-1]["content"]
    assert len(reviewed.review.findings) == 1 and not reviewed.escalated


async def test_support_that_stays_low_goes_to_a_person() -> None:
    model = ScriptedModel(*searches_then_submits(TWO_FINDINGS), calls(call(SUBMIT, TWO_FINDINGS)))

    reviewed = await graph_service(model, critic=critic_of([True, False], [True, False])).review(A_LISTING)

    assert reviewed.escalated
    assert reviewed.dropped_findings == 1


async def test_the_iteration_limit_forces_a_submission() -> None:
    model = ScriptedModel(
        *[calls(call("search_regulations", {"query": f"tema {i}"})) for i in range(2)],
        forced=calls(call(SUBMIT, A_REVIEW)),
    )

    reviewed = await graph_service(model, max_iterations=2).review(A_LISTING)

    assert reviewed.stop_reason == StopReason.MAX_ITERATIONS
    assert model.requests[-1]["force_tool"] == SUBMIT


async def test_the_same_call_failing_twice_forces_a_submission() -> None:
    model = ScriptedModel(
        calls(call("search_regulations", {})),
        calls(call("search_regulations", {})),
        forced=calls(call(SUBMIT, A_REVIEW)),
    )

    reviewed = await graph_service(model).review(A_LISTING)

    assert reviewed.stop_reason == StopReason.TOOL_ERROR


async def test_a_text_that_is_not_a_listing_ends_the_graph_before_the_critic() -> None:
    judge = critic_of()

    with pytest.raises(NotAListing):
        await graph_service(
            ScriptedModel(*searches_then_submits(review_with(is_listing=False, verdict="approve"))), critic=judge
        ).review(A_LISTING)

    assert judge.calls == 0


async def test_a_finished_run_leaves_nothing_in_the_checkpoint() -> None:
    # The checkpoint holds the listing's text: once the review is returned, it goes.
    checkpoints = Checkpoints()

    reviewed = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), checkpoints=checkpoints).review(
        A_LISTING
    )

    config = {"configurable": {"thread_id": reviewed.run_id}}
    assert await checkpoints.saver.aget_tuple(config) is None  # type: ignore[arg-type]


async def test_a_provider_outage_escapes_as_unavailable_and_still_cleans_up() -> None:
    class Down:
        async def complete_with_tools(
            self, *, messages: Any, tools: list[ToolSpec], force_tool: str | None = None
        ) -> Any:
            raise LLMUnavailable("both providers are down")

    checkpoints = Checkpoints()

    with pytest.raises(LLMUnavailable):
        await graph_service(Down(), checkpoints=checkpoints).review(A_LISTING)

    assert list(checkpoints.saver.list(None)) == []


async def test_the_graph_and_the_loop_return_the_same_review_for_the_same_answers() -> None:
    graph = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), critic=critic_of([True])).review(
        A_LISTING
    )
    loop = await AgentReviewService(
        ScriptedModel(*searches_then_submits(A_REVIEW)), FakeSearch(), critic=critic_of([True])
    ).review(A_LISTING)

    assert graph.review == loop.review
    assert [s.tool for s in graph.trace] == [s.tool for s in loop.trace]
    assert graph.usage.estimated_cost_usd == loop.usage.estimated_cost_usd
    assert loop.run_id is None and graph.run_id is not None


async def test_the_verdict_follows_the_findings_that_survive() -> None:
    reviewed = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), critic=critic_of([False])).review(
        A_LISTING
    )

    assert reviewed.review.verdict == Verdict.APPROVE


# ── The state is plain JSON ─────────────────────────────────────────────────────────────────


def test_usage_and_fragments_survive_a_json_round_trip() -> None:
    usage = LLMUsage("openai", "gpt-5.4-mini", 10, 2, 5, Decimal("0.0012"))
    fragments = {"36": fragment_to_json(a_fragment(36))}

    assert usage_from_json(json.loads(json.dumps(usage_to_json(usage)))) == usage
    assert fragments_from_json(json.loads(json.dumps(fragments))) == {36: a_fragment(36)}


def test_a_listing_state_is_json() -> None:
    assert json.loads(json.dumps(Listing(text="Piso", price_eur_month=Decimal(900)).model_dump(mode="json")))
