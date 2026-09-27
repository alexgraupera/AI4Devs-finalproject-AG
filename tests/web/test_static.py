from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from web.main import create_app


def test_serves_index_html_for_a_client_route(client: TestClient) -> None:
    for route in ("/", "/alquiler", "/alquiler/palma-santa-catalina-2h"):
        response = client.get(route)

        assert response.status_code == 200
        assert "<title>Umbral</title>" in response.text


def test_serves_a_built_asset(client: TestClient) -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('umbral')"


def test_a_missing_file_is_a_404_not_the_app(client: TestClient) -> None:
    response = client.get("/photos/missing.webp")

    assert response.status_code == 404


def test_never_serves_a_file_outside_the_build(client: TestClient) -> None:
    for path in ("/../secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/%2e%2e/secret.txt"):
        response = client.get(path)

        assert "outside the build" not in response.text


def test_unknown_bff_paths_are_a_404_not_the_app(client: TestClient) -> None:
    response = client.get("/bff/nothing-here")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_says_how_to_build_the_frontend_when_there_is_no_build(tmp_path: Path) -> None:
    app = create_app(Settings(), dist_dir=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404
    assert "npm --prefix frontend run build" in response.text
