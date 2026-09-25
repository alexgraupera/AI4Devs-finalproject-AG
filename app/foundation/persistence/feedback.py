"""Where feedback is kept: one row per vote, in the database the corpus already lives in."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_INSERT = text("""
    INSERT INTO feedback (request_id, kind, rating, comment)
    VALUES (:request_id, :kind, :rating, :comment)
    RETURNING id, created_at
""")


class PostgresFeedbackStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, *, request_id: UUID, kind: str, rating: str, comment: str | None) -> tuple[int, datetime]:
        async with self._sessions() as session, session.begin():
            row = (
                await session.execute(
                    _INSERT, {"request_id": request_id, "kind": kind, "rating": rating, "comment": comment}
                )
            ).one()
        return int(row.id), row.created_at
