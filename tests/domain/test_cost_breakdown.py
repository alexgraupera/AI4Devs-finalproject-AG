"""Where a review's cost goes: the breakdown sums to what the run was billed, step by step."""

from decimal import Decimal

from app.domain.agent_review_service import AgentReviewService
from app.domain.graph.state import step_of, usage_to_json
from app.domain.schemas.listing_agent_review import CostBreakdown, Step, TraceStep
from app.foundation.llm.usage import LLMUsage
from tests.domain.graph.test_listing_review_graph import graph_service, searches_then_submits
from tests.domain.test_agent_review_service import A_LISTING, critic_of, two_passes
from tests.generation.agentic.test_loop import A_REVIEW, ScriptedModel
from tests.generation.agentic.test_rewrite import ScriptedWriter
from tests.generation.agentic.test_tools import FakeSearch

ACTOR = LLMUsage("openai", "gpt-5.4-mini", 1_000, 100, 700, Decimal("0.002"))
CRITIC = LLMUsage("openai", "gpt-5.4-mini", 2_000, 200, 900, Decimal("0.0024"))


def test_the_calls_of_a_step_add_up_and_the_steps_keep_their_order() -> None:
    searches = [TraceStep(step=1, tool="search_regulations", latency_ms=120)] * 2

    breakdown = CostBreakdown.of([(Step.CRITIC, CRITIC), (Step.PLAN, ACTOR), (Step.PLAN, ACTOR)], searches)

    assert [s.step for s in breakdown.steps] == [Step.PLAN, Step.TOOLS, Step.CRITIC]
    plan = breakdown.steps[0]
    assert (plan.calls, plan.input_tokens, plan.estimated_cost_usd) == (2, 2_000, Decimal("0.004"))
    assert (breakdown.steps[1].calls, breakdown.steps[1].latency_ms) == (2, 240)
    assert breakdown.total.estimated_cost_usd == Decimal("0.0064")


def test_a_step_without_calls_is_omitted() -> None:
    breakdown = CostBreakdown.of([(Step.PLAN, ACTOR)]).add(Step.REWRITE, None)

    assert [s.step for s in breakdown.steps] == [Step.PLAN]


def test_a_call_recorded_before_the_breakdown_existed_belongs_to_the_actor() -> None:
    recorded = usage_to_json(ACTOR)
    del recorded["step"]

    assert step_of(recorded) == Step.PLAN
    assert step_of(usage_to_json(CRITIC, Step.CRITIC)) == Step.CRITIC


def assert_sums_to_the_usage(breakdown: CostBreakdown, usage: LLMUsage) -> None:
    total = breakdown.total
    assert (total.input_tokens, total.output_tokens) == (usage.input_tokens, usage.output_tokens)
    assert total.estimated_cost_usd == usage.estimated_cost_usd


async def test_the_loop_breaks_its_cost_down_by_actor_tools_critic_and_rewrite() -> None:
    writer = ScriptedWriter("Piso de dos habitaciones en Chamberí. Fianza de una mensualidad.")
    service = AgentReviewService(two_passes(A_REVIEW), FakeSearch(), critic=critic_of([True]), rewriter=writer)

    reviewed = await service.review(A_LISTING)

    assert [s.step for s in reviewed.cost.steps] == [Step.PLAN, Step.TOOLS, Step.CRITIC, Step.REWRITE]
    assert_sums_to_the_usage(reviewed.cost, reviewed.usage)


async def test_the_graph_breaks_its_cost_down_as_the_loop_does() -> None:
    graph = await graph_service(ScriptedModel(*searches_then_submits(A_REVIEW)), critic=critic_of([True])).review(
        A_LISTING
    )
    loop = await AgentReviewService(
        ScriptedModel(*searches_then_submits(A_REVIEW)), FakeSearch(), critic=critic_of([True])
    ).review(A_LISTING)

    assert_sums_to_the_usage(graph.cost, graph.usage)
    assert [(s.step, s.calls, s.estimated_cost_usd) for s in graph.cost.steps] == [
        (s.step, s.calls, s.estimated_cost_usd) for s in loop.cost.steps
    ]


def test_the_total_of_an_empty_breakdown_costs_nothing_known() -> None:
    assert CostBreakdown().total.estimated_cost_usd is None
