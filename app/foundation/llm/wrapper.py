"""The single door to the LLM.

Every call goes through here, so the model and the provider are configuration rather than
code: LiteLLM normalises the call, and Instructor validates the answer against a Pydantic
schema and re-prompts the model when it does not fit.

Provider failures are translated here into the domain's own errors, so nothing above this
module has to know what `litellm` raises.

Fallback between providers, cost accounting and structured logging land here too, in later
phases. Nothing above this module imports `litellm` or a provider SDK.
"""

from typing import Protocol, TypeVar

import instructor
import openai
from instructor.core import InstructorRetryException
from litellm import acompletion
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pydantic import BaseModel

from app.domain.errors import LLMUnavailable, ReviewGenerationError

T = TypeVar("T", bound=BaseModel)

# Provider trouble, not our trouble: retrying the same call later may well work.
_UNAVAILABLE = (Timeout, RateLimitError, ServiceUnavailableError, InternalServerError, APIConnectionError)


class StructuredLLM(Protocol):
    """What the domain needs from an LLM: an answer that already fits a schema."""

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> T: ...


class LLMWrapper:
    def __init__(self, model: str, max_retries: int = 2) -> None:
        self._model = model
        self._max_retries = max_retries
        # from_litellm picks the sync or async client from the callable it gets; acompletion is a
        # coroutine function, and async_client makes that explicit instead of inferred.
        self._client = instructor.from_litellm(acompletion, async_client=True)

    async def complete_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        try:
            return await self._client.chat.completions.create(
                model=self._model,
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
