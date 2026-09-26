"""The shared login in front of the UI: nothing shows before it, and production never runs without it."""

import pathlib

import pytest
from streamlit.testing.v1 import AppTest

import ui_api
import ui_auth
from app.config import get_settings

ROOT = pathlib.Path(__file__).parents[2]
REVIEW = str(ROOT / "pages" / "1_Revisión_de_anuncios.py")
HOME = str(ROOT / "streamlit_app.py")
USER, PASSWORD = "evaluador", "una-contraseña-larga"


@pytest.fixture(autouse=True)
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # On top of tests/ui/conftest.py, which starts every UI test with no login.
    monkeypatch.setenv("UI_USERNAME", USER)
    monkeypatch.setenv("UI_PASSWORD", PASSWORD)
    monkeypatch.setattr(ui_api, "is_api_available", lambda timeout=90: True)
    get_settings.cache_clear()


def opened(path: str = REVIEW) -> AppTest:
    return AppTest.from_file(path, default_timeout=30).run()


def sign_in(page: AppTest, user: str = USER, password: str = PASSWORD) -> AppTest:
    page.text_input(key="login-user").input(user)
    page.text_input(key="login-password").input(password)
    return next(b for b in page.button if b.label == "Entrar").click().run()


def shows_the_review_form(page: AppTest) -> bool:
    return any(area.label == "Pega aquí tu anuncio" for area in page.text_area)


def test_a_page_reached_by_its_own_url_shows_only_the_login() -> None:
    page = opened()

    assert page.title[0].value == ui_auth.TITLE
    assert not shows_the_review_form(page)


def test_the_right_credentials_open_the_page_and_offer_to_sign_out() -> None:
    page = sign_in(opened())

    assert shows_the_review_form(page)
    assert any(b.label == ui_auth.SIGN_OUT for b in page.sidebar.button)


def test_a_wrong_password_is_refused_without_saying_which_half_was_wrong() -> None:
    page = sign_in(opened(), password="otra")

    assert [e.value for e in page.error] == [ui_auth.WRONG]
    assert not shows_the_review_form(page)


def test_five_wrong_attempts_lock_the_session() -> None:
    page = opened()
    for _ in range(ui_auth.MAX_ATTEMPTS):
        page = sign_in(page, password="otra")

    assert [e.value for e in page.error] == [ui_auth.LOCKED]
    assert [e.value for e in page.run().error] == [ui_auth.LOCKED]
    assert not any(b.label == "Entrar" for b in page.button)


def test_signing_out_asks_for_the_credentials_again() -> None:
    page = sign_in(opened())

    page = next(b for b in page.sidebar.button if b.label == ui_auth.SIGN_OUT).click().run()

    assert page.title[0].value == ui_auth.TITLE
    assert not shows_the_review_form(page)


def test_the_home_page_is_guarded_too() -> None:
    assert opened(HOME).title[0].value == ui_auth.TITLE


def test_production_without_credentials_shows_nothing_but_the_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("UI_PASSWORD", "")
    get_settings.cache_clear()

    page = opened()

    assert [e.value for e in page.error] == [ui_auth.NOT_CONFIGURED]
    assert not shows_the_review_form(page)


def test_development_without_credentials_needs_no_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UI_USERNAME", "")
    monkeypatch.setenv("UI_PASSWORD", "")
    get_settings.cache_clear()

    assert shows_the_review_form(opened())
