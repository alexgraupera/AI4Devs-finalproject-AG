"""What a call costs, worked out from the model that actually answered.

Providers answer with the snapshot they served (`claude-haiku-4-5-20251001`), while this table
is keyed by the alias we ask for. An exact lookup alone would miss, price the call at zero, and
a cost dashboard would report that every request was free. A missing number is a gap; a zero is
a lie, so an unknown model returns None and says so in the logs.
"""

import logging
from decimal import Decimal

log = logging.getLogger(__name__)

# USD per million tokens (input, output). Taken from the providers' pricing pages on 2026-09-20:
# https://claude.com/pricing and https://developers.openai.com/api/docs/pricing
MODEL_COSTS: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "gpt-5.4-nano": (Decimal("0.20"), Decimal("1.25")),
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("4.50")),
    "gpt-5.4": (Decimal("2.50"), Decimal("15.00")),
}

_MILLION = Decimal(1_000_000)


def normalise_model(model: str) -> str:
    """Strip the provider prefix LiteLLM may carry: `anthropic/claude-haiku-4-5`."""
    return model.split("/", 1)[1] if "/" in model else model


def provider_of(model: str) -> str:
    name = normalise_model(model).lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3"):
        return "openai"
    return "unknown"


def price_for(model: str) -> tuple[Decimal, Decimal] | None:
    """Exact match, then the LONGEST matching prefix.

    The "longest" is load-bearing: `gpt-5.4-mini-2026-03-05` starts with both `gpt-5.4` and
    `gpt-5.4-mini`, and the shorter one would over-price a mini call by more than three times.
    """
    name = normalise_model(model)
    exact = MODEL_COSTS.get(name)
    if exact is not None:
        return exact

    candidates = [key for key in MODEL_COSTS if name.startswith(key)]
    if candidates:
        return MODEL_COSTS[max(candidates, key=len)]

    log.warning("llm.model_not_in_pricing_table", extra={"model": model})
    return None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Cost in USD, or None when the model is not in the table."""
    price = price_for(model)
    if price is None:
        return None
    input_price, output_price = price
    return (input_tokens * input_price + output_tokens * output_price) / _MILLION
