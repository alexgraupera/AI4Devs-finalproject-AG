"""The single door to the LLM.

Every call goes through here, so the model and the provider are configuration rather than
code: LiteLLM normalises the call, its Router moves to the second provider when the first one
fails, and Instructor validates the answer against a Pydantic schema, re-prompting when it
does not fit.

Provider failures are translated here into the domain's own errors, and what the call cost is
measured here too, so nothing above this module has to know what `litellm` raises or charges.
"""

import time
from typing import Any, Protocol, TypeVar

import instructor
import openai
import structlog
from instructor.core import InstructorRetryException
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
from app.foundation.llm.usage import LLMUsage, StructuredCompletion

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


def build_router(primary_model: str, fallback_model: str | None = None, num_retries: int = 2) -> Router:
    """One deployment per logical name, plus an explicit fallback edge between them."""
    model_list: list[dict[str, Any]] = [{"model_name": LOGICAL_MODEL, "litellm_params": {"model": primary_model}}]
    fallbacks: list[dict[str, list[str]]] = []

    if fallback_model:
        model_list.append({"model_name": FALLBACK_MODEL, "litellm_params": {"model": fallback_model}})
        fallbacks.append({LOGICAL_MODEL: [FALLBACK_MODEL]})

    return Router(model_list=model_list, fallbacks=fallbacks, num_retries=num_retries)


class LLMWrapper:
    def __init__(self, router: Router, max_retries: int = 2) -> None:
        self._router = router
        self._max_retries = max_retries
        # from_litellm picks the sync or async client from the callable it gets; Router.acompletion
        # is a coroutine function, and async_client makes that explicit instead of inferred.
        self._client = instructor.from_litellm(router.acompletion, async_client=True)

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> StructuredCompletion[T]:
        started = time.perf_counter()
        try:
            output, raw = await self._client.chat.completions.create_with_completion(
                model=LOGICAL_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_model=schema,
                max_retries=self._max_retries,
            )
        except InstructorRetryException as error:
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

        latency_ms = int((time.perf_counter() - started) * 1000)
        return StructuredCompletion(output=output, usage=self._usage_of(raw, latency_ms))

    def _usage_of(self, raw: Any, latency_ms: int) -> LLMUsage:
        """Read the usage off the raw completion, and price it.

        Known limit: when Instructor re-prompts on an invalid answer, the usage describes the
        FINAL attempt, not the sum of them, so a heavily retried call under-reports.
        """
        # The answering model is what the Router resolved, not the logical name we asked for.
        model = getattr(raw, "model", None) or LOGICAL_MODEL
        usage = getattr(raw, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return LLMUsage(
            provider=provider_of(model),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=estimate_cost(model, input_tokens, output_tokens),
        )
