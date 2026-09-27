"""The shared login of the demo in the web server (web/session.py): the pages are public, the tools are not."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.web.conftest import FakeApi, settings
from web.main import create_app
from web.session import COOKIE, LOCKED, NOT_CONFIGURED, SESSION_SECONDS, SIGN_IN_REQUIRED, WRONG, sign

USER = "evaluador"
PASSWORD = "una-contraseña-larga-de-verdad"
SECRET = "the-session-secret"
ASK = "/api/v1/regulations/ask"
A_QUESTION = {"question": "¿Cuál es la fianza legal?"}


class Clock:
    def __init__(self) -> None:
        self.now = 1_900_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


def web(api: FakeApi, dist: Path, clock: Clock, **overrides: object) -> TestClient:
    configured = {"ui_username": USER, "ui_password": PASSWORD, "session_secret": SECRET, **overrides}
    app = create_app(settings(**configured), dist_dir=dist, transport=httpx.MockTransport(api.handle), clock=clock)
    return TestClient(app)


@pytest.fixture
def login(api: FakeApi, dist: Path, clock: Clock) -> Iterator[TestClient]:
    with web(api, dist, clock) as client:
        yield client


# Any: Starlette's test client answers with whichever httpx it found (httpx2 when installed).
def sign_in(client: TestClient, password: str = PASSWORD) -> Any:
    return client.post("/bff/session", json={"username": USER, "password": password})


def test_the_right_credentials_set_a_signed_httponly_samesite_strict_session_cookie(
    login: TestClient, api: FakeApi, clock: Clock
) -> None:
    assert login.get("/bff/session").json() == {"login_required": True, "signed_in": False}

    response = sign_in(login)

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert f"{COOKIE}={sign(SECRET, USER, int(clock.now) + SESSION_SECONDS)}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert f"Max-Age={SESSION_SECONDS}" in cookie
    assert login.get("/bff/session").json() == {"login_required": True, "signed_in": True}
    assert login.post(ASK, json=A_QUESTION).status_code == 200
    assert len(api.received) == 1


def test_a_wrong_password_answers_401_with_the_message(login: TestClient) -> None:
    response = sign_in(login, password="not-it")

    assert response.status_code == 401
    assert response.json()["error"] == {"code": "wrong_credentials", "message": WRONG}
    assert COOKIE not in response.headers.get("set-cookie", "")


def test_five_failures_lock_the_client_for_a_minute(login: TestClient, clock: Clock) -> None:
    answers = [sign_in(login, password="not-it") for _ in range(5)]

    assert [answer.status_code for answer in answers] == [401, 401, 401, 401, 429]
    assert answers[-1].json()["error"]["message"] == LOCKED
    # Locked means locked: the right password does not open it early.
    assert sign_in(login).status_code == 429

    clock.now += 61

    assert sign_in(login).status_code == 204


def test_the_lock_is_per_client(login: TestClient) -> None:
    other = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(5):
        sign_in(login, password="not-it")

    response = login.post("/bff/session", json={"username": USER, "password": PASSWORD}, headers=other)

    assert response.status_code == 204


def test_a_forwarded_call_without_a_session_answers_401(login: TestClient, api: FakeApi) -> None:
    response = login.post(ASK, json=A_QUESTION)

    assert response.status_code == 401
    assert response.json()["error"] == {"code": "sign_in_required", "message": SIGN_IN_REQUIRED}
    assert api.received == []
    # The pages stay public: fictional listings cost nothing to show.
    assert login.get("/alquiler").status_code == 200


def test_a_tampered_or_expired_cookie_is_refused(login: TestClient, clock: Clock, api: FakeApi) -> None:
    expires = int(clock.now) + SESSION_SECONDS
    forged = sign("another-secret", USER, expires)
    login.cookies.set(COOKIE, forged)
    assert login.post(ASK, json=A_QUESTION).status_code == 401

    later = sign(SECRET, USER, expires)
    login.cookies.set(COOKIE, f"{expires + 3600}.{later.partition('.')[2]}")
    assert login.post(ASK, json=A_QUESTION).status_code == 401

    login.cookies.set(COOKIE, sign(SECRET, USER, expires))
    clock.now = expires + 1
    assert login.post(ASK, json=A_QUESTION).status_code == 401
    assert api.received == []


@pytest.mark.parametrize("missing", ["ui_username", "ui_password", "session_secret"])
def test_production_without_credentials_or_secret_fails_closed(
    api: FakeApi, dist: Path, clock: Clock, missing: str
) -> None:
    with web(api, dist, clock, environment="production", **{missing: ""}) as client:
        for response in (client.get("/bff/session"), sign_in(client), client.post(ASK, json=A_QUESTION)):
            assert response.status_code == 503
            assert response.json()["error"]["message"] == NOT_CONFIGURED
    assert api.received == []


def test_production_marks_the_cookie_secure(api: FakeApi, dist: Path, clock: Clock) -> None:
    with web(api, dist, clock, environment="production") as client:
        assert "Secure" in sign_in(client).headers["set-cookie"]


def test_development_without_credentials_needs_no_login(api: FakeApi, dist: Path, clock: Clock) -> None:
    with web(api, dist, clock, ui_username="", ui_password="", session_secret="") as client:
        assert client.get("/bff/session").json() == {"login_required": False, "signed_in": False}
        assert client.post(ASK, json=A_QUESTION).status_code == 200


def test_signing_out_clears_the_cookie(login: TestClient) -> None:
    sign_in(login)

    response = login.delete("/bff/session")

    assert response.status_code == 204
    assert f'{COOKIE}=""' in response.headers["set-cookie"]
    assert login.get("/bff/session").json()["signed_in"] is False
    assert login.post(ASK, json=A_QUESTION).status_code == 401
