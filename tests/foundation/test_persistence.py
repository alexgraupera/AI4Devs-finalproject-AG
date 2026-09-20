from typing import Any, Self, cast

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.foundation.persistence.database import check_connection, create_engine, database_status, session_factory

A_URL = "postgresql+asyncpg://rental:rental@localhost:5432/rental"


class FakeConnection:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.statements: list[str] = []

    async def __aenter__(self) -> Self:
        if self.error is not None:
            raise self.error
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: Any) -> None:
        self.statements.append(str(statement))


class FakeEngine:
    def __init__(self, error: Exception | None = None) -> None:
        self.connection = FakeConnection(error)

    def connect(self) -> FakeConnection:
        return self.connection


def engine_of(fake: FakeEngine) -> AsyncEngine:
    return cast(AsyncEngine, fake)


def a_connection_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_builds_the_engine_from_the_configured_url() -> None:
    engine = create_engine(A_URL)

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "rental"


def test_the_session_factory_binds_the_engine() -> None:
    engine = create_engine(A_URL)

    assert session_factory(engine).kw["bind"] is engine


async def test_a_working_connection_is_reported_as_healthy() -> None:
    fake = FakeEngine()

    assert await check_connection(engine_of(fake)) is True
    assert fake.connection.statements == ["SELECT 1"]


@pytest.mark.parametrize("error", [a_connection_error(), OSError("name or service not known")])
async def test_a_failing_connection_answers_instead_of_raising(error: Exception) -> None:
    assert await check_connection(engine_of(FakeEngine(error=error))) is False


async def test_reports_the_store_as_disabled_when_it_is_not_configured() -> None:
    assert await database_status(None) == "disabled"


async def test_reports_the_store_as_unavailable_when_it_cannot_be_reached() -> None:
    assert await database_status(engine_of(FakeEngine(error=a_connection_error()))) == "unavailable"


async def test_reports_the_store_as_ok_when_it_answers() -> None:
    assert await database_status(engine_of(FakeEngine())) == "ok"
