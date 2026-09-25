from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_agent_review_service
from app.domain.agent_review_service import AgentReviewService
from app.generation.agentic.loop import SUBMIT
from app.main import create_app
from tests.generation.agentic.test_loop import A_REVIEW, ScriptedModel, call, calls
from tests.generation.agentic.test_tools import FakeSearch

A_LISTING = {
    "text": (
        "Piso de dos habitaciones en Chamberí, con ascensor. Fianza de dos meses y honorarios a cargo del inquilino."
    ),
    "municipality": "Madrid",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    model = ScriptedModel(
        calls(call("search_regulations", {"query": "fianza"}), content="Busco la fianza"), calls(call(SUBMIT, A_REVIEW))
    )
    app = create_app()
    app.dependency_overrides[get_agent_review_service] = lambda: AgentReviewService(model, FakeSearch())
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_returns_findings_with_citations_the_trace_and_the_cost(client: TestClient) -> None:
    response = client.post("/api/v1/listings/agent-review", json=A_LISTING)

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "request_changes"
    assert body["stop_reason"] == "completed"
    assert body["findings"][0]["citations"][0]["url"].endswith("#a36")
    assert [step["tool"] for step in body["trace"]] == ["search_regulations", SUBMIT]
    assert body["trace"][0]["thought"] == "Busco la fianza"
    assert body["usage"]["estimated_cost_usd"] == "0.004"


def test_an_empty_listing_is_rejected_before_the_agent_runs(client: TestClient) -> None:
    response = client.post("/api/v1/listings/agent-review", json={"text": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_text"
