from decimal import Decimal
from typing import Any

import pytest
from instructor.core import IncompleteOutputException, InstructorRetryException
from litellm.exceptions import RateLimitError

from app.domain.errors import LLMUnavailable, ReviewGenerationError
from app.domain.schemas.listing_review import ListingReview, Verdict
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
