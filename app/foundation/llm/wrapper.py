"""The single door to the LLM.

Every call goes through here, so the model and the provider are configuration rather than
code: LiteLLM normalises the call, its Router moves to the second provider when the first one
fails, and Instructor validates the answer against a Pydantic schema, re-prompting when it
does not fit.

Provider failures are translated here into the domain's own errors, and what the call cost is
measured here too, so nothing above this module has to know what `litellm` raises or charges.
"""

import json
import time
from typing import Any, Protocol, TypeVar

import instructor
import openai
import structlog
from instructor.core import IncompleteOutputException, InstructorRetryException
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from litellm.router import Router
from pydantic import BaseModel

from app.domain.errors import LLMUnavailable, ReviewGenerationError
from app.foundation.llm.pricing import estimate_cost, provider_of
from app.foundation.llm.tools import RequestedToolCall, ToolCompletion, ToolSpec
from app.foundation.llm.usage import LLMUsage, StructuredCompletion, UsageAccumulator, current_usage

log = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# The name the code asks for. Which model answers is the Router's business, not the caller's.
LOGICAL_MODEL = "listing-reviewer"
FALLBACK_MODEL = f"{LOGICAL_MODEL}-fallback"

# Provider trouble, not our trouble: the same call may well work on the other provider, or later.
_UNAVAILABLE = (Timeout, RateLimitError, ServiceUnavailableError, InternalServerError, APIConnectionError)


class StructuredLLM(Protocol):
    """What the domain needs from an LLM: an answer that already fits a schema, and its cost."""

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]: ...


def build_router(
    primary_model: str,
    fallback_model: str | None = None,
    num_retries: int = 2,
    *,
    timeout_seconds: float | None = None,
) -> Router:
    """One deployment per logical name, plus an explicit fallback edge between them.

    One router per role (generator, judge, reranker), built in the composition root: each role has
    its own primary and its own fallback, and the code that asks never names either.

    `drop_params` lets one call carry a temperature to a model that rejects it (the reasoning ones
    only accept their default) instead of failing: the parameter is dropped for that model only.
    """
    params: dict[str, Any] = {"drop_params": True}
    if timeout_seconds is not None:
        params["timeout"] = timeout_seconds

    model_list: list[dict[str, Any]] = [
        {"model_name": LOGICAL_MODEL, "litellm_params": {"model": primary_model, **params}}
    ]
    fallbacks: list[dict[str, list[str]]] = []

    if fallback_model:
        model_list.append({"model_name": FALLBACK_MODEL, "litellm_params": {"model": fallback_model, **params}})
        fallbacks.append({LOGICAL_MODEL: [FALLBACK_MODEL]})

    return Router(model_list=model_list, fallbacks=fallbacks, num_retries=num_retries, timeout=timeout_seconds)


class LLMWrapper:
    def __init__(
        self,
        router: Router,
        max_retries: int = 2,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self._router = router
        self._max_retries = max_retries
        # A hard budget per call, not a style instruction: an answer that hits it is truncated
        # and treated as a failure (see `llm.truncated`), never returned half-written.
        self._max_tokens = max_tokens
        self._temperature = temperature
        # from_litellm picks the sync or async client from the callable it gets; Router.acompletion
        # is a coroutine function, and async_client makes that explicit instead of inferred.
        self._client = instructor.from_litellm(router.acompletion, async_client=True)
        # Instructor fires this once per attempt, re-prompts included, which is the only way to
        # bill a call for everything it actually spent instead of for its last try.
        self._client.on("completion:response", _record_attempt)

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        started = time.perf_counter()
        accumulator = UsageAccumulator()
        token = current_usage.set(accumulator)
        options: dict[str, Any] = {}
        if self._max_tokens is not None:
            options["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            options["temperature"] = self._temperature
        try:
            output, raw = await self._client.chat.completions.create_with_completion(
                model=LOGICAL_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_model=schema,
                max_retries=self._max_retries,
                **options,
            )
        except IncompleteOutputException as error:
            # The model ran out of tokens mid-answer. A truncated structure must never reach a
            # user, and it must not look like "the model is bad" in the logs either: it is a
            # budget that is too small for the task, and it is named as such.
            log.warning("llm.truncated", schema=schema.__name__, max_tokens=self._max_tokens)
            raise ReviewGenerationError(f"the answer was truncated at {self._max_tokens} tokens") from error
        except InstructorRetryException as error:
            if isinstance(error.__cause__, IncompleteOutputException):
                log.warning("llm.truncated", schema=schema.__name__, max_tokens=self._max_tokens)
                raise ReviewGenerationError(f"the answer was truncated at {self._max_tokens} tokens") from error
            # Instructor exhausted its re-prompts. It wraps whatever ended the attempts, so a
            # provider outage in disguise must not be reported as a bad answer from the model.
            if isinstance(error.__cause__, _UNAVAILABLE):
                raise LLMUnavailable(str(error)) from error
            raise ReviewGenerationError(str(error)) from error
        except _UNAVAILABLE as error:
            raise LLMUnavailable(str(error)) from error
        except openai.APIError as error:
            # Every LiteLLM provider error derives from this one. What is left here (bad request,
            # auth, unknown model) is ours to fix, not something worth retrying.
            raise ReviewGenerationError(str(error)) from error
        finally:
            current_usage.reset(token)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return StructuredCompletion(output=output, usage=usage_of(accumulator, raw, latency_ms))

    async def complete_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
        force_tool: str | None = None,
    ) -> ToolCompletion:
        """One turn of an agent: the model answers or asks for tools. The code runs them, not this.

        The same Router, fallback and error translation as `complete_structured`. There is no
        Instructor here: the structure of a tool call is the provider's, and its arguments are
        validated by the tool that receives them, which is what can tell the model what was wrong.
        """
        started = time.perf_counter()
        options: dict[str, Any] = {
            "tools": [tool.as_openai() for tool in tools],
            "tool_choice": {"type": "function", "function": {"name": force_tool}} if force_tool else "auto",
        }
        if self._max_tokens is not None:
            options["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            options["temperature"] = self._temperature

        try:
            # Never streamed (no `stream` option), so the response is a complete ModelResponse;
            # the Router's signature covers both shapes, hence the Any.
            response: Any = await self._router.acompletion(
                model=LOGICAL_MODEL,
                messages=messages,  # type: ignore[arg-type]
                **options,
            )
        except _UNAVAILABLE as error:
            raise LLMUnavailable(str(error)) from error
        except openai.APIError as error:
            raise ReviewGenerationError(str(error)) from error

        choice = response.choices[0]
        if choice.finish_reason == "length":
            log.warning("llm.truncated", schema="tool_call", max_tokens=self._max_tokens)
            raise ReviewGenerationError(f"the agent turn was truncated at {self._max_tokens} tokens")

        message = choice.message
        raw_calls = list(message.tool_calls or [])
        assistant: dict[str, Any] = {"role": "assistant", "content": message.content}
        if raw_calls:
            assistant["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments or "{}"},
                }
                for call in raw_calls
            ]

        model = str(getattr(response, "model", None) or LOGICAL_MODEL)
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return ToolCompletion(
            content=message.content,
            tool_calls=[_requested(call) for call in raw_calls],
            usage=LLMUsage(
                provider=provider_of(model),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=int((time.perf_counter() - started) * 1000),
                estimated_cost_usd=estimate_cost(model, input_tokens, output_tokens),
            ),
            message=assistant,
        )


def _requested(call: Any) -> RequestedToolCall:
    """Arguments arrive as a JSON string. Invalid JSON is kept, so the model can be told so."""
    raw = call.function.arguments or "{}"
    try:
        arguments = json.loads(raw)
    except json.JSONDecodeError:
        return RequestedToolCall(id=call.id, name=call.function.name, malformed=raw)
    if not isinstance(arguments, dict):
        return RequestedToolCall(id=call.id, name=call.function.name, malformed=raw)
    return RequestedToolCall(id=call.id, name=call.function.name, arguments=arguments)


def _record_attempt(response: Any) -> None:
    accumulator = current_usage.get()
    if accumulator is not None:
        accumulator.record(response)


def usage_of(accumulator: UsageAccumulator, raw: Any, latency_ms: int) -> LLMUsage:
    """Price a call by everything it spent, attempts included.

    The accumulator is fed by the per-attempt hook. When no attempt was recorded (a client that
    does not fire hooks), it falls back to the final completion, which is better than reporting
    nothing at all.
    """
    if accumulator.attempts == 0:
        accumulator.record(raw)

    # The answering model is what the Router resolved, not the logical name we asked for.
    model = accumulator.model or getattr(raw, "model", None) or LOGICAL_MODEL
    input_tokens = accumulator.input_tokens
    output_tokens = accumulator.output_tokens

    return LLMUsage(
        provider=provider_of(model),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimate_cost(model, input_tokens, output_tokens),
        attempts=max(accumulator.attempts, 1),
    )
