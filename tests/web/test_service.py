import httpx
from fastapi.testclient import TestClient

from tests.web.conftest import API_URL, FakeApi


def test_reports_the_api_up(client: TestClient, api: FakeApi) -> None:
    api.answer = lambda request: httpx.Response(200, json={"status": "ok"})

    response = client.get("/bff/service")

    assert response.json() == {"api": "up"}
    assert [str(request.url) for request in api.received] == [f"{API_URL}/health"]


def test_reports_the_api_down_when_it_does_not_answer(client: TestClient, api: FakeApi) -> None:
    def asleep(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no answer", request=request)

    api.answer = asleep

    assert client.get("/bff/service").json() == {"api": "down"}


def test_reports_the_api_down_when_it_answers_with_an_error(client: TestClient, api: FakeApi) -> None:
    api.answer = lambda request: httpx.Response(503)

    assert client.get("/bff/service").json() == {"api": "down"}


def test_its_own_liveness_never_calls_the_api(client: TestClient, api: FakeApi) -> None:
    response = client.get("/healthz")

    assert response.json() == {"status": "ok"}
    assert api.received == []
