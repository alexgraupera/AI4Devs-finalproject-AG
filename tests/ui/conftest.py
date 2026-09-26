"""Every UI test starts from the same settings, whatever a developer's `.env` says: no login."""

from collections.abc import Iterator

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def no_login_by_default(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("UI_USERNAME", "")
    monkeypatch.setenv("UI_PASSWORD", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
