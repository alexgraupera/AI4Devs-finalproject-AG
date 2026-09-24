"""Production refuses to start without the secrets it cannot run safely without."""

import pytest

from app.config import Settings
from app.main import MissingProductionSettings, create_app

COMPLETE = {
    "api_key": "key",
    "service_token": "token",
    "anthropic_api_key": "sk-ant",
    "openai_api_key": "sk-openai",
    "database_url": "postgresql+asyncpg://db/rental",
    "redis_url": "redis://cache:6379/0",
}


def production(**overrides: str) -> Settings:
    return Settings.model_validate({"environment": "production", **COMPLETE, **overrides})


def test_development_starts_with_every_secret_empty() -> None:
    assert Settings(environment="development").missing_for_production() == []


def test_production_starts_with_every_secret_set() -> None:
    assert production().missing_for_production() == []


@pytest.mark.parametrize(
    ("field", "name"),
    [
        ("api_key", "API_KEY"),
        ("service_token", "SERVICE_TOKEN"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        ("openai_api_key", "OPENAI_API_KEY"),
        ("database_url", "DATABASE_URL"),
        ("redis_url", "REDIS_URL"),
    ],
)
def test_production_names_each_missing_secret(field: str, name: str) -> None:
    settings = production(**{field: ""})

    assert settings.missing_for_production() == [name]


def test_the_app_refuses_to_start_in_production_with_a_secret_missing() -> None:
    with pytest.raises(MissingProductionSettings, match="SERVICE_TOKEN"):
        create_app(production(service_token=""))


def test_the_refusal_names_the_setting_and_never_a_value() -> None:
    with pytest.raises(MissingProductionSettings) as refused:
        create_app(production(api_key=""))

    assert str(refused.value) == "production cannot start without: API_KEY"


@pytest.mark.parametrize(
    "url",
    [
        "postgres://rental:secret@db:5432/rental",
        "postgresql://rental:secret@db:5432/rental",
        "postgresql+asyncpg://rental:secret@db:5432/rental",
    ],
)
def test_the_database_url_always_uses_the_async_driver(url: str) -> None:
    # Hosting platforms hand out the plain spelling; the service speaks asyncpg.
    assert Settings(database_url=url).database_url == "postgresql+asyncpg://rental:secret@db:5432/rental"


def test_an_empty_database_url_stays_empty() -> None:
    assert Settings(database_url="").database_url == ""
