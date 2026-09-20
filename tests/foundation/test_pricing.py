from decimal import Decimal

import pytest

from app.foundation.llm.pricing import estimate_cost, normalise_model, price_for, provider_of


def test_strips_the_provider_prefix() -> None:
    assert normalise_model("anthropic/claude-haiku-4-5") == "claude-haiku-4-5"
    assert normalise_model("claude-haiku-4-5") == "claude-haiku-4-5"


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("anthropic/claude-haiku-4-5", "anthropic"),
        ("openai/gpt-5.4-mini", "openai"),
        ("something-else", "unknown"),
    ],
)
def test_reads_the_provider_from_the_model(model: str, provider: str) -> None:
    assert provider_of(model) == provider


def test_prices_a_known_model() -> None:
    assert price_for("anthropic/claude-haiku-4-5") == (Decimal("1.00"), Decimal("5.00"))


def test_prices_a_dated_snapshot_with_the_longest_matching_prefix() -> None:
    # gpt-5.4-mini-2026-03-05 starts with gpt-5.4 too: the shorter prefix would over-price it.
    assert price_for("gpt-5.4-mini-2026-03-05") == MINI_PRICE
    assert price_for("claude-haiku-4-5-20251001") == (Decimal("1.00"), Decimal("5.00"))


MINI_PRICE = (Decimal("0.75"), Decimal("4.50"))


def test_returns_none_for_an_unknown_model() -> None:
    assert price_for("llama-99") is None
    assert estimate_cost("llama-99", 1000, 1000) is None


def test_estimates_the_cost_of_a_call() -> None:
    # 1000 input tokens at 1 USD/MTok + 500 output tokens at 5 USD/MTok.
    assert estimate_cost("anthropic/claude-haiku-4-5", 1_000, 500) == Decimal("0.0035")
