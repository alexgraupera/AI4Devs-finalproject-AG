"""Feedback kept in PostgreSQL, on its own database: the migration and the store together (#51)."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.foundation.persistence.database import create_engine, session_factory
from app.foundation.persistence.feedback import PostgresFeedbackStore
from tests import database
from tests.database import DATABASE_URL, SKIP_REASON

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason=SKIP_REASON)

FEEDBACK_URL = database.database_url("feedback")


@pytest.fixture(scope="session", autouse=True)
def feedback_database() -> None:
    database.create_database(FEEDBACK_URL)
    database.migrate(FEEDBACK_URL)


async def test_a_vote_is_kept_and_read_back_with_its_request() -> None:
    engine = create_engine(FEEDBACK_URL)
    rated = uuid4()
    try:
        id, created_at = await PostgresFeedbackStore(session_factory(engine)).save(
            request_id=rated, kind="regulation_answer", rating="down", comment="Cita el artículo equivocado"
        )
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text("SELECT request_id, kind, rating, comment FROM feedback WHERE id = :id"), {"id": id}
                )
            ).one()
    finally:
        await engine.dispose()

    assert created_at is not None
    assert (row.request_id, row.kind, row.rating, row.comment) == (
        rated,
        "regulation_answer",
        "down",
        "Cita el artículo equivocado",
    )


async def test_the_table_refuses_a_kind_or_a_rating_it_does_not_know() -> None:
    engine = create_engine(FEEDBACK_URL)
    store = PostgresFeedbackStore(session_factory(engine))
    try:
        with pytest.raises(IntegrityError):
            await store.save(request_id=uuid4(), kind="weather", rating="up", comment=None)
        with pytest.raises(IntegrityError):
            await store.save(request_id=uuid4(), kind="listing_review", rating="meh", comment=None)
    finally:
        await engine.dispose()


def test_the_database_is_its_own() -> None:
    # Never the configured one: these tests write rows.
    assert FEEDBACK_URL != DATABASE_URL
    assert asyncio.iscoroutinefunction(PostgresFeedbackStore.save)
