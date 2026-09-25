from decimal import Decimal
from typing import Any

import pytest
from instructor.core import IncompleteOutputException, InstructorRetryException
from litellm.exceptions import RateLimitError

from app.domain.errors import LLMUnavailable, ReviewGenerationError
from app.domain.schemas.listing_review import ListingReview, Verdict
from app.foundation.llm.tools import ToolSpec
from app.foundation.llm.usage import UsageAccumulator, current_usage
from app.foundation.llm.wrapper import (
    FALLBACK_MODEL,
    LOGICAL_MODEL,
    LLMWrapper,
    build_router,
    usage_of,
)


class FakeCompletions:
    """Stands in for Instructor's client: returns a canned answer, or raises.

    `attempts` are the responses the per-attempt hook would see, so a re-prompted call can be
    reproduced without a network.
    """

    def __init__(self, raw: Any = None, error: Exception | None = None, attempts: list[Any] | None = None) -> None:
        self.raw = raw
        self.error = error
        self.attempts = attempts or ([raw] if raw is not None else [])
        self.called_with: dict[str, Any] | None = None

    async def create_with_completion(self, **kwargs: Any) -> tuple[ListingReview, Any]:
        self.called_with = kwargs
        accumulator = current_usage.get()
        if accumulator is not None:
            for attempt in self.attempts:
                accumulator.record(attempt)
        if self.error is not None:
            raise self.error
        return ListingReview(findings=[], verdict=Verdict.APPROVE, summary="Todo correcto"), self.raw


class Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class RawCompletion:
    def __init__(self, model: str, prompt_tokens: int = 1_000, completion_tokens: int = 500) -> None:
        self.model = model
        self.usage = Usage(prompt_tokens, completion_tokens)


def wrapper_with(
    completions: FakeCompletions, *, max_tokens: int | None = None, temperature: float | None = None
) -> LLMWrapper:
    wrapper = LLMWrapper.__new__(LLMWrapper)
    wrapper._max_retries = 2
    wrapper._max_tokens = max_tokens
    wrapper._temperature = temperature
    wrapper._client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    return wrapper


async def complete(wrapper: LLMWrapper) -> Any:
    return await wrapper.complete_structured(system="system", user="user", schema=ListingReview)


def test_builds_the_router_with_primary_and_fallback_deployments() -> None:
    router = build_router(primary_model="anthropic/claude-haiku-4-5", fallback_model="openai/gpt-5.4-mini")

    names = [deployment["model_name"] for deployment in router.model_list]
    assert names == [LOGICAL_MODEL, FALLBACK_MODEL]
    assert router.fallbacks == [{LOGICAL_MODEL: [FALLBACK_MODEL]}]


def test_every_deployment_carries_the_timeout_and_drops_unsupported_parameters() -> None:
    router = build_router(
        primary_model="anthropic/claude-haiku-4-5", fallback_model="openai/gpt-5.4-mini", timeout_seconds=45
    )

    for deployment in router.model_list:
        assert deployment["litellm_params"]["timeout"] == 45
        # A reasoning model rejects a temperature; the parameter is dropped for it, not the call.
        assert deployment["litellm_params"]["drop_params"] is True


def test_builds_a_router_without_fallback_when_it_is_not_configured() -> None:
    router = build_router(primary_model="anthropic/claude-haiku-4-5", fallback_model=None)

    assert [deployment["model_name"] for deployment in router.model_list] == [LOGICAL_MODEL]
    # The Router stores no fallbacks as None rather than an empty list.
    assert not router.fallbacks


async def test_asks_the_router_for_the_logical_model() -> None:
    completions = FakeCompletions(RawCompletion("claude-haiku-4-5"))

    await complete(wrapper_with(completions))

    assert completions.called_with is not None
    assert completions.called_with["model"] == LOGICAL_MODEL


async def test_reports_the_usage_of_the_model_that_answered() -> None:
    completions = FakeCompletions(RawCompletion("claude-haiku-4-5-20251001", 1_000, 500))

    usage = (await complete(wrapper_with(completions))).usage

    assert usage.provider == "anthropic"
    assert usage.model == "claude-haiku-4-5-20251001"
    assert usage.input_tokens == 1_000
    assert usage.output_tokens == 500
    assert usage.estimated_cost_usd is not None
    assert usage.latency_ms >= 0


async def test_reports_the_fallback_provider_when_it_answered() -> None:
    completions = FakeCompletions(RawCompletion("gpt-5.4-mini"))

    usage = (await complete(wrapper_with(completions))).usage

    assert usage.provider == "openai"


async def test_leaves_the_cost_empty_for_a_model_outside_the_table() -> None:
    completions = FakeCompletions(RawCompletion("llama-99"))

    assert (await complete(wrapper_with(completions))).usage.estimated_cost_usd is None


async def test_reports_a_provider_outage_as_unavailable() -> None:
    error = RateLimitError("rate limited", llm_provider="anthropic", model="claude-haiku-4-5")

    with pytest.raises(LLMUnavailable):
        await complete(wrapper_with(FakeCompletions(error=error)))


async def test_reports_an_exhausted_re_prompt_as_a_generation_error() -> None:
    error = InstructorRetryException("no valid answer", n_attempts=2, total_usage=0)

    with pytest.raises(ReviewGenerationError):
        await complete(wrapper_with(FakeCompletions(error=error)))


async def test_looks_past_instructor_when_the_real_cause_is_the_provider() -> None:
    cause = RateLimitError("rate limited", llm_provider="anthropic", model="claude-haiku-4-5")
    error = InstructorRetryException("gave up", n_attempts=2, total_usage=0)
    error.__cause__ = cause

    with pytest.raises(LLMUnavailable):
        await complete(wrapper_with(FakeCompletions(error=error)))


async def test_bills_every_attempt_of_a_re_prompted_call() -> None:
    # The model answered twice: the first answer did not fit the schema, both were billed.
    completions = FakeCompletions(
        raw=RawCompletion("claude-haiku-4-5", 1_100, 200),
        attempts=[
            RawCompletion("claude-haiku-4-5", 1_000, 300),
            RawCompletion("claude-haiku-4-5", 1_100, 200),
        ],
    )

    usage = (await complete(wrapper_with(completions))).usage

    assert usage.attempts == 2
    assert usage.input_tokens == 2_100
    assert usage.output_tokens == 500
    # 2100 input at 1 USD/MTok + 500 output at 5 USD/MTok.
    assert usage.estimated_cost_usd == Decimal("0.0046")


async def test_reports_one_attempt_when_the_answer_fits_the_first_time() -> None:
    completions = FakeCompletions(RawCompletion("claude-haiku-4-5", 1_000, 500))

    assert (await complete(wrapper_with(completions))).usage.attempts == 1


async def test_falls_back_to_the_final_completion_when_no_attempt_was_recorded() -> None:
    raw = RawCompletion("claude-haiku-4-5", 1_000, 500)

    usage = usage_of(UsageAccumulator(), raw, latency_ms=10)

    assert usage.attempts == 1
    assert usage.input_tokens == 1_000


def test_isolates_the_accumulator_of_each_call() -> None:
    assert current_usage.get() is None


async def test_the_token_budget_and_the_temperature_reach_the_call() -> None:
    completions = FakeCompletions(RawCompletion("claude-haiku-4-5"))

    await complete(wrapper_with(completions, max_tokens=4_000, temperature=0.0))

    assert completions.called_with is not None
    assert completions.called_with["max_tokens"] == 4_000
    assert completions.called_with["temperature"] == 0.0


async def test_nothing_is_sent_for_the_bounds_that_are_not_configured() -> None:
    completions = FakeCompletions(RawCompletion("claude-haiku-4-5"))

    await complete(wrapper_with(completions))

    assert completions.called_with is not None
    assert "max_tokens" not in completions.called_with
    assert "temperature" not in completions.called_with


async def test_a_truncated_answer_is_a_generation_error_never_a_half_structure() -> None:
    with pytest.raises(ReviewGenerationError, match="truncated"):
        await complete(wrapper_with(FakeCompletions(error=IncompleteOutputException()), max_tokens=4_000))


async def test_a_truncation_behind_the_re_prompts_is_still_named_a_truncation() -> None:
    error = InstructorRetryException("gave up", n_attempts=2, total_usage=0)
    error.__cause__ = IncompleteOutputException()

    with pytest.raises(ReviewGenerationError, match="truncated"):
        await complete(wrapper_with(FakeCompletions(error=error), max_tokens=4_000))


# ── Tool calling ────────────────────────────────────────────────────────────────────────────


class Function:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class ToolCall:
    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id = id
        self.function = Function(name, arguments)


class Message:
    def __init__(self, content: str | None, tool_calls: list[ToolCall] | None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class Choice:
    def __init__(self, message: Message, finish_reason: str = "tool_calls") -> None:
        self.message = message
        self.finish_reason = finish_reason


class ToolResponse:
    def __init__(
        self, message: Message, *, model: str = "claude-haiku-4-5-20251001", finish_reason: str = "tool_calls"
    ) -> None:
        self.choices = [Choice(message, finish_reason)]
        self.model = model
        self.usage = Usage(2_000, 150)


class FakeRouter:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs: dict[str, Any] = {}

    async def acompletion(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


def tool_wrapper(router: FakeRouter, **options: Any) -> LLMWrapper:
    wrapper = wrapper_with(FakeCompletions(), **options)
    wrapper._router = router  # type: ignore[assignment]
    return wrapper


SEARCH_SPEC = ToolSpec(name="search_regulations", description="Busca", parameters={"type": "object", "properties": {}})


async def complete_tools(wrapper: LLMWrapper, force_tool: str | None = None) -> Any:
    return await wrapper.complete_with_tools(
        messages=[{"role": "user", "content": "hola"}], tools=[SEARCH_SPEC], force_tool=force_tool
    )


async def test_returns_the_requested_tool_calls_with_their_arguments_parsed() -> None:
    message = Message("Busco la fianza", [ToolCall("c1", "search_regulations", '{"query": "fianza"}')])

    completion = await complete_tools(tool_wrapper(FakeRouter(ToolResponse(message))))

    assert completion.content == "Busco la fianza"
    assert [(c.id, c.name, c.arguments) for c in completion.tool_calls] == [
        ("c1", "search_regulations", {"query": "fianza"})
    ]


async def test_carries_the_assistant_message_forward_with_its_tool_calls() -> None:
    message = Message(None, [ToolCall("c1", "search_regulations", '{"query": "fianza"}')])

    completion = await complete_tools(tool_wrapper(FakeRouter(ToolResponse(message))))

    assert completion.message["role"] == "assistant"
    assert completion.message["tool_calls"][0]["id"] == "c1"


async def test_malformed_arguments_are_surfaced_instead_of_raising() -> None:
    message = Message(None, [ToolCall("c1", "search_regulations", "{not json")])

    (call,) = (await complete_tools(tool_wrapper(FakeRouter(ToolResponse(message))))).tool_calls

    assert call.malformed == "{not json"
    assert call.arguments == {}


async def test_prices_the_turn_by_the_model_that_answered() -> None:
    usage = (await complete_tools(tool_wrapper(FakeRouter(ToolResponse(Message("ok", None)))))).usage

    assert usage.provider == "anthropic"
    assert usage.input_tokens == 2_000
    assert usage.estimated_cost_usd is not None


async def test_sends_the_tools_and_forces_one_when_asked() -> None:
    router = FakeRouter(ToolResponse(Message(None, [ToolCall("c1", "search_regulations", "{}")])))

    await complete_tools(tool_wrapper(router, max_tokens=4_000), force_tool="search_regulations")

    assert router.kwargs["tools"] == [SEARCH_SPEC.as_openai()]
    assert router.kwargs["tool_choice"] == {"type": "function", "function": {"name": "search_regulations"}}
    assert router.kwargs["max_tokens"] == 4_000


async def test_a_truncated_agent_turn_is_a_generation_error() -> None:
    router = FakeRouter(ToolResponse(Message("a medias", None), finish_reason="length"))

    with pytest.raises(ReviewGenerationError, match="truncated"):
        await complete_tools(tool_wrapper(router, max_tokens=100))


async def test_a_provider_outage_during_a_tool_call_is_unavailable() -> None:
    error = RateLimitError("rate limited", llm_provider="anthropic", model="claude-haiku-4-5")

    with pytest.raises(LLMUnavailable):
        await complete_tools(tool_wrapper(FakeRouter(error=error)))
