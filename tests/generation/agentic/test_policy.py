"""Least privilege and the audit: pure table checks, and the dispatcher in front of the tools."""

from typing import Any

import pytest

from app.foundation.llm.tools import RequestedToolCall, ToolSpec
from app.generation.agentic import policy
from app.generation.agentic.loop import ToolBox
from app.generation.agentic.policy import AgentRole, may_call, redact
from app.generation.agentic.tools import ToolResult


class PublishListing:
    """A tool with a side effect, registered but granted to nobody."""

    spec = ToolSpec(name="publish_listing", description="Publica el anuncio", parameters={"type": "object"})

    def __init__(self) -> None:
        self.ran = False

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        self.ran = True
        return ToolResult(ok=True, content="Publicado")


class RecordingLog:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def info(self, event: str, **fields: Any) -> None:
        self.events.append({"event": event, **fields})

    def warning(self, event: str, **fields: Any) -> None:
        self.info(event, **fields)


def test_the_reviewer_may_search_check_and_submit() -> None:
    assert all(may_call(AgentRole.REVIEWER, t) for t in ("check_listing_fields", "search_regulations", "submit_review"))


def test_the_critic_and_the_rewriter_may_call_nothing() -> None:
    assert not may_call(AgentRole.CRITIC, "search_regulations")
    assert not may_call(AgentRole.REWRITER, "check_listing_fields")


def test_a_tool_nobody_was_granted_is_denied_by_default() -> None:
    assert not may_call(AgentRole.REVIEWER, "publish_listing")


async def test_a_denied_call_never_reaches_the_tool_and_is_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    # What a prompt injection in a pasted listing would try: a tool the reviewer was never granted.
    recording = RecordingLog()
    monkeypatch.setattr(policy, "log", recording)
    publish = PublishListing()

    result, _ = await ToolBox([publish]).execute(RequestedToolCall(id="c", name="publish_listing"))

    assert not publish.ran
    assert not result.ok and "Llamada denegada" in result.content
    assert recording.events[0]["outcome"] == "denied"


def test_a_tool_the_role_cannot_call_is_not_even_offered() -> None:
    assert [spec.name for spec in ToolBox([PublishListing()]).specs] == ["submit_review"]


async def test_an_allowed_call_is_audited_with_its_arguments_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generation.agentic.tools import SearchRegulations
    from tests.generation.agentic.test_tools import FakeSearch

    recording = RecordingLog()
    monkeypatch.setattr(policy, "log", recording)

    await ToolBox([SearchRegulations(FakeSearch())]).execute(
        RequestedToolCall(id="c", name="search_regulations", arguments={"query": "fianza", "jurisdictions": ["state"]})
    )

    (event,) = recording.events
    assert event["outcome"] == "allowed" and event["role"] == "reviewer"
    assert event["arguments"] == {"query": "fianza", "jurisdictions": "<list, 1>"}


def test_the_listing_text_never_reaches_the_audit() -> None:
    assert redact({"listing_text": "Llama al 612 345 678"}) == {"listing_text": "<str, 20>"}
