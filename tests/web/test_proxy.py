import json

import httpx
from fastapi.testclient import TestClient

from tests.web.conftest import API_KEY, API_URL, SERVICE_TOKEN, FakeApi
from web.forwarding import UNREACHABLE

ASK = "/api/v1/regulations/ask"
A_QUESTION = {"question": "¿Cuál es la fianza legal?", "jurisdictions": ["state"]}


def test_forwards_an_allowed_call_with_the_service_token_and_the_api_key(client: TestClient, api: FakeApi) -> None:
    answer = {"answer": "Una mensualidad."}
    api.answer = lambda request: httpx.Response(200, json=answer, headers={"X-Request-ID": "r-1"})

    response = client.post(ASK, json=A_QUESTION)

    assert response.status_code == 200
    assert response.json() == {"answer": "Una mensualidad."}
    assert response.headers["x-request-id"] == "r-1"
    [sent] = api.received
    assert str(sent.url) == f"{API_URL}{ASK}"
    assert sent.headers["X-Service-Token"] == SERVICE_TOKEN
    assert sent.headers["X-API-Key"] == API_KEY
    assert json.loads(sent.content) == A_QUESTION


def test_the_feedback_is_forwarded_too(client: TestClient, api: FakeApi) -> None:
    api.answer = lambda request: httpx.Response(201, json={"id": 1})

    response = client.post("/api/v1/feedback", json={"request_id": "r-1", "kind": "regulation_answer", "rating": "up"})

    assert response.status_code == 201
    assert [str(request.url) for request in api.received] == [f"{API_URL}/api/v1/feedback"]


def test_forwards_the_listing_review(client: TestClient, api: FakeApi) -> None:
    api.answer = lambda request: httpx.Response(200, json={"verdict": "approve", "findings": []})
    listing = {"text": "Piso de 2 habitaciones en Ruzafa, 1.100 €/mes, fianza de un mes.", "price_eur_month": 1100}

    response = client.post("/api/v1/listings/review", json=listing)

    assert response.status_code == 200
    [sent] = api.received
    assert str(sent.url) == f"{API_URL}/api/v1/listings/review"
    assert sent.headers["X-API-Key"] == API_KEY
    assert json.loads(sent.content) == listing


def test_forwards_the_agent_review_and_passes_a_202_through(client: TestClient, api: FakeApi) -> None:
    # 202: the agent paused the review and it waits for a person. The frontend reads that status.
    paused = {"status": "waiting_human", "run_id": "run-1"}
    api.answer = lambda request: httpx.Response(202, json=paused)

    response = client.post("/api/v1/listings/agent-review", json={"text": "Piso de 2 habitaciones en Chamberí."})

    assert response.status_code == 202
    assert response.json() == paused
    assert [str(request.url) for request in api.received] == [f"{API_URL}/api/v1/listings/agent-review"]


def test_forwards_the_pending_review_and_the_decision_with_the_run_id_in_the_path(
    client: TestClient, api: FakeApi
) -> None:
    run_id = "2f1c0b8e-5a4d-4c3b-9e2f-1a2b3c4d5e6f"
    decision = {"action": "adjust", "keep": [0, 2], "note": "La fianza sí es un problema."}

    pending = client.get(f"/api/v1/listings/agent-review/{run_id}")
    resumed = client.post(f"/api/v1/listings/agent-review/{run_id}/resume", json=decision)

    assert pending.status_code == resumed.status_code == 200
    first, second = api.received
    assert (first.method, str(first.url)) == ("GET", f"{API_URL}/api/v1/listings/agent-review/{run_id}")
    assert (second.method, str(second.url)) == ("POST", f"{API_URL}/api/v1/listings/agent-review/{run_id}/resume")
    assert json.loads(second.content) == decision
    assert second.headers["X-Service-Token"] == SERVICE_TOKEN


def test_refuses_a_run_id_that_tries_to_reach_another_endpoint(client: TestClient, api: FakeApi) -> None:
    for path in (
        "/api/v1/listings/agent-review/%2E%2E%2F%2E%2E%2Fregulations%2Fsearch",
        "/api/v1/listings/agent-review/run-1%2F..%2F..%2Fregulations%2Fask/resume",
        "/api/v1/listings/agent-review/run-1/resume/extra",
    ):
        assert client.get(path).status_code == 404
        assert client.post(path, json={"action": "approve"}).status_code == 404
    assert api.received == []


def test_passes_the_api_status_code_and_error_body_through(client: TestClient, api: FakeApi) -> None:
    body = {"error": {"code": "rate_limited", "message": "Demasiadas consultas seguidas."}}
    api.answer = lambda request: httpx.Response(429, json=body, headers={"Retry-After": "42"})

    response = client.post(ASK, json=A_QUESTION)

    assert response.status_code == 429
    assert response.json() == body
    assert response.headers["retry-after"] == "42"


def test_answers_404_for_a_path_outside_the_allow_list(client: TestClient, api: FakeApi) -> None:
    # The search is an API endpoint, but not one the marketplace uses: it is not forwarded.
    outside = client.post("/api/v1/regulations/search", json={"query": "fianza"})
    wrong_method = client.get(ASK)

    for response in (outside, wrong_method):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert api.received == []


def test_answers_502_with_the_spanish_message_when_the_api_is_unreachable(client: TestClient, api: FakeApi) -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    api.answer = unreachable

    response = client.post(ASK, json=A_QUESTION)

    assert response.status_code == 502
    assert response.json() == {"error": {"code": "api_unreachable", "message": UNREACHABLE}}
