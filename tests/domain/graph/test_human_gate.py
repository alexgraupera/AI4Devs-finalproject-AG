"""The pause before publishing: a review the critic could not back waits for a person."""

from typing import Any

import pytest

from app.domain.agent_review_service import AgentReviewService
from app.domain.errors import RunNotFound, RunNotWaiting
from app.domain.schemas.listing_agent_review import HumanAction, HumanDecision
from app.generation.agentic.loop import SUBMIT
from tests.domain.graph.test_listing_review_graph import Checkpoints, searches_then_submits
from tests.domain.test_agent_review_service import A_LISTING, critic_of, finding, review_with
from tests.generation.agentic.test_loop import A_REVIEW, ScriptedModel, call, calls
from tests.generation.agentic.test_tools import FakeSearch

# Two findings, the second never backed: the boss retries once, then escalates.
TWO = review_with(
    finding(legal_basis="LAU art. 36.1", sources=[36]),
    {**finding(legal_basis="LAU art. 36.1", sources=[36]), "message": "Inventada"},
)


def escalating(checkpoints: Checkpoints) -> AgentReviewService:
    model = ScriptedModel(*searches_then_submits(TWO), calls(call(SUBMIT, TWO)))
    return AgentReviewService(
        model, FakeSearch(), critic=critic_of([True, False], [True, False]), checkpoints=checkpoints
    )


async def paused(checkpoints: Checkpoints) -> tuple[AgentReviewService, Any]:
    service = escalating(checkpoints)
    return service, await service.review(A_LISTING)


async def test_an_escalated_review_pauses_before_publishing() -> None:
    _, reviewed = await paused(Checkpoints())

    assert reviewed.pending_review is not None
    assert reviewed.pending_review.run_id == reviewed.run_id
    assert [f.message for f in reviewed.pending_review.proposed.findings] == ["La fianza supera una mensualidad"]
    assert [r.message for r in reviewed.pending_review.rejected] == ["Inventada"]


async def test_a_paused_run_stays_in_the_checkpoint() -> None:
    checkpoints = Checkpoints()
    _, reviewed = await paused(checkpoints)

    assert await checkpoints.saver.aget_tuple({"configurable": {"thread_id": reviewed.run_id}}) is not None


async def test_an_accepted_review_does_not_pause() -> None:
    service = AgentReviewService(
        ScriptedModel(*searches_then_submits(A_REVIEW)),
        FakeSearch(),
        critic=critic_of([True]),
        checkpoints=Checkpoints(),
    )

    reviewed = await service.review(A_LISTING)

    assert reviewed.pending_review is None


async def test_approving_publishes_the_proposed_review_and_cleans_up() -> None:
    checkpoints = Checkpoints()
    service, reviewed = await paused(checkpoints)

    done = await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.APPROVE))

    assert done.pending_review is None
    assert [f.message for f in done.review.findings] == ["La fianza supera una mensualidad"]
    assert done.human_decision is not None and done.human_decision.action == HumanAction.APPROVE
    assert await checkpoints.saver.aget_tuple({"configurable": {"thread_id": reviewed.run_id}}) is None


async def test_adjusting_keeps_only_the_findings_the_person_chose() -> None:
    service, reviewed = await paused(Checkpoints())

    done = await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.ADJUST, keep=[], note="No aplica"))

    assert done.review.findings == []


async def test_rejecting_discards_the_review() -> None:
    service, reviewed = await paused(Checkpoints())

    done = await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.REJECT))

    assert done.review.findings == []
    assert done.human_decision is not None and done.human_decision.action == HumanAction.REJECT


async def test_a_paused_review_can_be_read_again() -> None:
    service, reviewed = await paused(Checkpoints())

    again = await service.pending(reviewed.run_id)

    assert again.pending_review is not None
    assert again.pending_review.proposed == reviewed.pending_review.proposed


async def test_resuming_a_run_that_does_not_exist_is_not_found() -> None:
    service = escalating(Checkpoints())

    with pytest.raises(RunNotFound):
        await service.resume("no-such-run", HumanDecision(action=HumanAction.APPROVE))


async def test_resuming_twice_finds_nothing_to_resume() -> None:
    service, reviewed = await paused(Checkpoints())
    await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.APPROVE))

    with pytest.raises(RunNotFound):
        await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.APPROVE))


async def test_a_run_that_is_not_waiting_cannot_be_resumed() -> None:
    # A run that finished without pausing is deleted; one that still has a checkpoint but no pending
    # node would be "not waiting". Built here by resuming, then writing a finished state back.
    checkpoints = Checkpoints()
    service, reviewed = await paused(checkpoints)
    graph, _ = await service._compiled()
    config = {"configurable": {"thread_id": reviewed.run_id}}
    await graph.aupdate_state(config, {"outcome": "accept"}, as_node="human_gate")  # type: ignore[arg-type]

    with pytest.raises(RunNotWaiting):
        await service.resume(reviewed.run_id, HumanDecision(action=HumanAction.APPROVE))


def test_adjusting_must_say_which_findings_stand() -> None:
    with pytest.raises(ValueError, match="keep"):
        HumanDecision(action=HumanAction.ADJUST)
