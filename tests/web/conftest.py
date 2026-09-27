"""The web server with a fake API behind it: every test sees what reached the API, and never the network."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from web.main import create_app

API_URL = "http://api.test"
SERVICE_TOKEN = "the-service-token"
API_KEY = "the-api-key"

Answer = Callable[[httpx.Request], httpx.Response]


@dataclass
class FakeApi:
    """Answers with `answer` and keeps every request it received."""

    answer: Answer = field(default=lambda request: httpx.Response(200, json={"ok": True}))
    received: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.received.append(request)
        return self.answer(request)


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Umbral</title>", encoding="utf-8")
    (build / "assets" / "app.js").write_text("console.log('umbral')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the build", encoding="utf-8")
    return build


def settings(**overrides: object) -> Settings:
    """Everything a test does not name is set here, never read from a developer's `.env`."""
    values: dict[str, object] = {
        "environment": "development",
        "api_url": API_URL,
        "service_token": SERVICE_TOKEN,
        "api_key": API_KEY,
        "ui_username": "",
        "ui_password": "",
        "session_secret": "",
    }
    return Settings(**{**values, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def client(api: FakeApi, dist: Path) -> Iterator[TestClient]:
    app = create_app(settings(), dist_dir=dist, transport=httpx.MockTransport(api.handle))
    with TestClient(app) as test_client:
        yield test_client
