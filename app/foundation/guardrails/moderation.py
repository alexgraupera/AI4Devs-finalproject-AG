"""Moderation through LiteLLM, so provider access stays behind one door.

Two decisions worth stating:

- The classifier is OpenAI's, and it is free, but it still needs a key. When there is none the
  service runs without this layer instead of failing to start: the other three input layers do
  not depend on a provider.
- When the call itself fails (outage, wrong model name, quota), the review continues and the
  failure is logged. Moderation protects us from abusive text, and a listing review is not worth
  taking the whole product down for; the alternative, failing closed, turns a provider incident
  into a full outage.
"""

import logging

from litellm import amoderation

log = logging.getLogger(__name__)

# OpenAI retired `text-moderation-latest`; the omni model is the current one.
DEFAULT_MODERATION_MODEL = "omni-moderation-latest"


class LiteLLMModeration:
    def __init__(self, model: str = DEFAULT_MODERATION_MODEL) -> None:
        self._model = model

    async def is_flagged(self, text: str) -> bool:
        try:
            response = await amoderation(input=text, model=self._model)
        except Exception:
            log.warning("guardrail.moderation_unavailable", exc_info=True)
            return False
        return any(result.flagged for result in response.results)


class DisabledModeration:
    """Used when no provider key is configured: every text passes this layer."""

    async def is_flagged(self, text: str) -> bool:
        return False
