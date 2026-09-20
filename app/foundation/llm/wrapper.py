"""The single door to the LLM.

Every call goes through here, so the model and the provider are configuration rather than
code: LiteLLM normalises the call, and Instructor validates the answer against a Pydantic
schema and re-prompts the model when it does not fit.

Fallback between providers, cost accounting and structured logging land here too, in later
phases. Nothing above this module imports `litellm` or a provider SDK.
"""

from typing import Protocol, TypeVar

import instructor
from litellm import acompletion
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
        return await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_model=schema,
            max_retries=self._max_retries,
        )
