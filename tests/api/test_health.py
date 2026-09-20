from fastapi.testclient import TestClient

from rental_assistant.api.app import create_app


def test_returns_ok_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
