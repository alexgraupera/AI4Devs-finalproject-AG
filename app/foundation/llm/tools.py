"""Function calling, in the service's own words.

The model never runs anything. It returns text that asks for a tool by name with some arguments;
the code decides whether to run it, runs it, and hands the result back as the next message. These
types are that exchange, independent of the provider: LiteLLM normalises Anthropic's and OpenAI's
tool calls into one shape, and the rest of the service only ever sees this one.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.foundation.llm.usage import LLMUsage


@dataclass(frozen=True)
class ToolSpec:
    """What the model is told about a tool. The description is a prompt: write it like one."""

    name: str
    description: str
    parameters: dict[str, Any]

    def as_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


@dataclass(frozen=True)
class RequestedToolCall:
    """A call the model asked for. `malformed` holds the raw arguments when they were not JSON."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    malformed: str | None = None


@dataclass(frozen=True)
class ToolCompletion:
    """One turn of the model: what it said, what it asked to run, what it cost.

    `message` is the assistant message exactly as the conversation must carry it forward, tool
    calls included: a provider rejects a tool result whose call is missing from the history.
    """

    content: str | None
    tool_calls: list[RequestedToolCall]
    usage: LLMUsage
    message: dict[str, Any]


class ToolCallingLLM(Protocol):
    async def complete_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: str | None = None,
    ) -> ToolCompletion: ...
