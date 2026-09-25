"""The thumbs under a review, through Streamlit's own test runner: the vote survives the rerun (#51)."""

import pathlib
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

import ui_api
import ui_feedback

PAGE = pathlib.Path(__file__).parents[2] / "pages" / "1_Revisión_de_anuncios.py"

A_REVIEW = {
    "request_id": "11111111-1111-1111-1111-111111111111",
    "findings": [],
    "verdict": "approve",
    "summary": "Todo en orden.",
    "usage": {
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "input_tokens": 1,
        "output_tokens": 1,
        "latency_ms": 1,
        "estimated_cost_usd": "0.001",
        "attempts": 1,
    },
    "cached": False,
}


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    sent: list[tuple[str, dict[str, Any]]] = []

    def post(path: str, payload: dict[str, Any], *, timeout: float = 120) -> tuple[dict[str, Any], None]:
        sent.append((path, payload))
        return (A_REVIEW if path.endswith("/review") else {"id": 1}), None

    monkeypatch.setattr(ui_api, "is_api_available", lambda timeout=90: True)
    monkeypatch.setattr(ui_api, "post", post)
    monkeypatch.setattr(ui_feedback, "post", post)
    return sent


def test_a_vote_is_sent_with_the_request_id_and_the_review_stays_on_screen(
    calls: list[tuple[str, dict[str, Any]]],
) -> None:
    page = AppTest.from_file(str(PAGE), default_timeout=30).run()
    page.text_area[0].input("Piso de dos habitaciones en Chamberí, con ascensor. Fianza de un mes.")
    page.button[0].click().run()

    page.text_input[-1].input("No ha visto la fianza")
    next(b for b in page.button if b.label.startswith("👎")).click().run()

    assert calls[-1] == (
        "/api/v1/feedback",
        {
            "request_id": A_REVIEW["request_id"],
            "kind": "listing_review",
            "rating": "down",
            "comment": "No ha visto la fianza",
        },
    )
    assert ui_feedback.THANKS in [caption.value for caption in page.caption]
    assert any("Todo en orden." in block.value for block in page.markdown)


def test_a_result_is_voted_once(calls: list[tuple[str, dict[str, Any]]]) -> None:
    page = AppTest.from_file(str(PAGE), default_timeout=30).run()
    page.text_area[0].input("Piso de dos habitaciones en Chamberí, con ascensor. Fianza de un mes.")
    page.button[0].click().run()
    next(b for b in page.button if b.label.startswith("👍")).click().run()

    assert not any(b.label.startswith("👍") for b in page.button)
    assert [path for path, _ in calls].count("/api/v1/feedback") == 1
